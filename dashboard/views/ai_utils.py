
"""
AI and Groq-related utility functions for the dashboard app.
Handles AI-powered answer generation, query responses, and grading feedback.
Updated to use Groq (Llama 3) instead of OpenAI/Grok.
"""

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
import re
import os
import mimetypes
import logging
import io
import base64
from django.db import models as djmodels
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from dotenv import load_dotenv

from ..models import StudentAnswer, Query, ExamAnswer

logger = logging.getLogger(__name__)

# Load environment variables and configure Groq
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = None
if GROQ_API_KEY:
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
else:
    logger.warning("⚠️ GROQ_API_KEY not configured. AI features will not work.")


def clean_ai_text(text: str) -> str:
    """Remove common markdown/heading artifacts from output."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = text.replace("##", "").replace("#", "")
    return text.strip()


def collect_attachments_from_instance(instance):
    """
    Inspect a Django model instance and return a list of attachments (bytes + metadata)
    for any FileField/ImageField the instance owns.
    Returns: list of dicts: [{'name': ..., 'mime_type': ..., 'data_b64': '...'}]
    """
    attachments = []
    try:
        for field in instance._meta.get_fields():
            # we only want actual File/Image fields
            if isinstance(field, (djmodels.FileField, djmodels.ImageField)):
                file_field = getattr(instance, field.name)
                if not file_field:
                    continue
                try:
                    # open in binary and read bytes
                    file_field.open(mode='rb')
                    data = file_field.read()
                    filename = os.path.basename(file_field.name or field.name)
                    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                    
                    data_b64 = base64.b64encode(data).decode('utf-8')
                    
                    attachments.append({
                        "name": filename,
                        "mime_type": mime_type,
                        "data_b64": data_b64
                    })
                    file_field.close()
                except Exception as e:
                    logger.exception("Failed reading file field %s on %s: %s", field.name, instance, e)
                    # continue reading other fields
    except Exception as e:
        logger.exception("collect_attachments_from_instance error: %s", e)
    return attachments


def build_groq_messages(text_prompt: str, attachments: list):
    """
    Build input 'messages' for client.chat.completions.create().
    `text_prompt` - the primary textual prompt (string)
    `attachments` - list of dicts {name,mime_type,data_b64}
    Returns list of messages.
    """
    content = []
    
    if text_prompt:
        content.append({"type": "text", "text": text_prompt})
        
    for att in attachments or []:
        # Groq (via OpenAI SDK) expects data URL for images
        mime = att.get("mime_type", "application/octet-stream")
        if mime.startswith('image/'):
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{att.get('data_b64')}"
                }
            })
        else:
            # For non-image files, we might just append a note or content if text
            # But mostly vision models handle images. 
            pass

    return [{"role": "user", "content": content}]


@csrf_exempt
def generate_answer_assign(request):
    """
    Endpoint for assign_question.html → returns {"answer": "..."}.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    
    if not client:
        return JsonResponse({"error": "Groq API not configured."}, status=500)

    question = (request.POST.get("question") or "").strip()
    if not question:
        return JsonResponse({"error": "No question provided."}, status=400)

    try:
        prompt = f"You are a subject expert. Create a clear, step-by-step solution for this assignment question:\n\n{question}"
        attachments = []
        if request.FILES:
            for f in request.FILES.getlist("attachments"):
                try:
                    data = b"".join(chunk for chunk in f.chunks())
                    mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                    data_b64 = base64.b64encode(data).decode('utf-8')
                    attachments.append({"name": f.name, "mime_type": mime, "data_b64": data_b64})
                except Exception:
                    logger.exception("Failed to read uploaded file %s", f.name)

        messages = build_groq_messages(prompt, attachments)
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1000
        )

        raw = response.choices[0].message.content
        return JsonResponse({"answer": clean_ai_text(raw)})
    except Exception as e:
        logger.exception("generate_answer_assign error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_answer_query(request):
    """
    Endpoint for respond_query.html → returns {"answer": "..."}.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    if not client:
        return JsonResponse({"error": "Groq API not configured."}, status=500)

    question_text = (request.POST.get("question") or "").strip()
    query_id = request.POST.get("query_id") or request.POST.get("id")

    attachments = []
    if query_id:
        try:
            q_obj = Query.objects.get(id=query_id)
            if not question_text:
                question_text = q_obj.query_text or question_text
            attachments = collect_attachments_from_instance(q_obj)
        except Query.DoesNotExist:
            logger.warning("Query id %s not found", query_id)

    if request.FILES:
        for f in request.FILES.getlist("attachments"):
            try:
                data = b"".join(chunk for chunk in f.chunks())
                mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                data_b64 = base64.b64encode(data).decode('utf-8')
                attachments.append({"name": f.name, "mime_type": mime, "data_b64": data_b64})
            except Exception:
                logger.exception("Failed to read uploaded file %s", f.name)

    if not question_text and not attachments:
        return JsonResponse({"error": "No query text or attachments provided."}, status=400)

    try:
        prompt = f"You are a teacher. Respond to this student query politely, explain step-by-step, and clear the student's doubt:\n\n{question_text}"
        messages = build_groq_messages(prompt, attachments)
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1000
        )

        raw = response.choices[0].message.content
        return JsonResponse({"answer": clean_ai_text(raw)})
    except Exception as e:
        logger.exception("generate_answer_query error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_remark_feedback(request):
    """
    Endpoint for remarks.html → returns {"feedback": "..."}.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    if not client:
        return JsonResponse({"error": "Groq API not configured."}, status=500)

    answer_id = request.POST.get("answer_id") or request.POST.get("id")
    answer_type = (request.POST.get("answer_type") or "").lower()
    question_text = (request.POST.get("question") or "").strip()
    student_answer_text = (request.POST.get("answer") or request.POST.get("student_answer") or "").strip()

    attachments = []
    instance = None

    if answer_id:
        if answer_type == "exam":
            try:
                instance = ExamAnswer.objects.select_related('question', 'exam', 'student_name').get(id=answer_id)
            except ExamAnswer.DoesNotExist:
                instance = None
        else:
            try:
                instance = StudentAnswer.objects.select_related('question', 'student_name').get(id=answer_id)
            except StudentAnswer.DoesNotExist:
                instance = None

    if instance:
        try:
            if not question_text:
                q = getattr(instance, 'question', None)
                if q:
                    question_text = getattr(q, 'description', None) or getattr(q, 'text', '') or question_text

            if not student_answer_text:
                student_answer_text = getattr(instance, 'answer_text', '') or student_answer_text

            attachments = collect_attachments_from_instance(instance)
        except Exception:
            logger.exception("Error extracting from instance in generate_remark_feedback")

    if request.FILES:
        for f in request.FILES.getlist("attachments"):
            try:
                data = b"".join(chunk for chunk in f.chunks())
                mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                data_b64 = base64.b64encode(data).decode('utf-8')
                attachments.append({"name": f.name, "mime_type": mime, "data_b64": data_b64})
            except Exception:
                logger.exception("Failed to read uploaded file %s", f.name)

    if not question_text and not student_answer_text and not attachments:
        return JsonResponse({"error": "Question and answer required."}, status=400)

    base_prompt = (
        f"You are a careful grader / teacher.\n\n"
        f"Question: {question_text}\n\n"
        f"Student's Answer: {student_answer_text}\n\n"
        f"Provide short, constructive feedback as a teacher's remark: point out errors (if any), "
        f"give a concise explanation of the issue, and suggest exact improvements or next steps."
    )

    try:
        messages = build_groq_messages(base_prompt, attachments)
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=500
        )

        raw = response.choices[0].message.content
        return JsonResponse({"feedback": clean_ai_text(raw)})
    except Exception as e:
        logger.exception("generate_remark_feedback error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def download_pdf(request):
    """Convert generated content to downloadable PDF"""
    if request.method == "POST":
        content = request.POST.get("content", "No content")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()

        title_style = styles["Heading1"]
        heading_style = styles["Heading2"]
        normal_style = styles["Normal"]

        story = []
        story.append(Paragraph("Generated Answer", title_style))
        story.append(Spacer(1, 12))

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.endswith(":"):  # treat as heading
                story.append(Paragraph(line, heading_style))
            else:
                story.append(Paragraph(line, normal_style))
            story.append(Spacer(1, 6))

        doc.build(story)
        buffer.seek(0)

        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = "attachment; filename=generated_answer.pdf"
        return response


@csrf_exempt
def generate_practice_questions(request):
    """
    Endpoint for generating practice questions via AI.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    if not client:
        return JsonResponse({"error": "Groq API not configured."}, status=500)

    topic = request.POST.get("topic", "").strip()
    difficulty = request.POST.get("difficulty", "Medium").strip()

    if not topic:
        return JsonResponse({"error": "Topic is required."}, status=400)

    try:
        prompt = (
            f"You are an expert tutor. Create 5 {difficulty}-level practice questions "
            f"on the topic '{topic}' for a student. "
            f"Format the output as a numbered list. "
            f"Do not provide the answers immediately, just the questions."
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800
        )
        
        raw = response.choices[0].message.content
        if raw:
            return JsonResponse({"questions": clean_ai_text(raw)})
        
        return JsonResponse({"error": "No questions generated."}, status=500)
    except Exception as e:
        logger.exception("generate_practice_questions error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_exam_questions(request):
    """
    Endpoint for generating exam questions via AI.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    if not client:
        return JsonResponse({"error": "Groq API not configured."}, status=500)

    class_name = request.POST.get("class_name", "").strip()
    try:
        easy_count = int(request.POST.get("easy_count") or 0)
        medium_count = int(request.POST.get("medium_count") or 0)
        hard_count = int(request.POST.get("hard_count") or 0)
    except ValueError:
        return JsonResponse({"error": "Invalid count values. Please use numbers."}, status=400)

    if not class_name:
        return JsonResponse({"error": "Class is required."}, status=400)

    subject = request.POST.get("subject", "").strip()
    chapter = request.POST.get("chapter", "").strip()

    total_count = easy_count + medium_count + hard_count
    if total_count == 0:
         return JsonResponse({"error": "At least one question must be selected."}, status=400)

    prompt = (
        f"You are a teacher creating a test for {class_name}.\n"
    )
    if subject:
        prompt += f"Subject: {subject}\n"
    if chapter:
        prompt += f"Chapter/Topic: {chapter}\n"
        
    prompt += (
        f"Generate exactly the following questions based on difficulty:\n"
        f"- {easy_count} Easy questions\n"
        f"- {medium_count} Medium questions\n"
        f"- {hard_count} Hard questions\n\n"
        f"Output MUST be a valid JSON array of objects. Do NOT include markdown formatting (like ```json), just the raw JSON.\n"
        f"Each object must have these keys:\n"
        f"- 'text': The question string (no numbering).\n"
        f"- 'marks': Integer suggested marks (e.g. 2 for Easy, 5 for Medium, 10 for Hard).\n"
        f"- 'type': String 'Easy', 'Medium', or 'Hard'.\n"
        f"- 'latex': (Optional) LaTeX string if math is involved, else empty string.\n"
        f"Example format: [{{'text': 'What is 5+5?', 'marks': 2, 'type': 'Easy', 'latex': ''}}]"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.7
        )
        
        raw_text = response.choices[0].message.content
        
        # Use regex to find the JSON array block since models can be chatty
        import re
        import json
        
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        
        cleaned_text = ""
        questions_json = []

        if json_match:
            try:
                cleaned_text = json_match.group(0)
                questions_json = json.loads(cleaned_text)
            except json.JSONDecodeError:
                # If regex fails (e.g. multiple blocks or malformed), try cleaning the raw text
                cleaned_text = raw_text.strip()
                if cleaned_text.startswith("```json"):
                    cleaned_text = cleaned_text[7:]
                elif cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text[3:]
                
                if cleaned_text.endswith("```"):
                    cleaned_text = cleaned_text[:-3]
                cleaned_text = cleaned_text.strip()
        else:
             # Fallback to standard cleaning if regex finds nothing
            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()

        try:
            if not questions_json:
                questions_json = json.loads(cleaned_text)
            
            if not isinstance(questions_json, list):
                 return JsonResponse({"error": "AI returned invalid format (not a list)."}, status=500)
            return JsonResponse({"questions": questions_json})
        except json.JSONDecodeError:
            logger.error(f"JSON Decode Error for AI text: {raw_text}")
            return JsonResponse({"error": "Failed to parse AI response as JSON."}, status=500)
            
    except Exception as e:
        logger.exception("generate_exam_questions error: %s", e)
        return JsonResponse({"error": f"Error: {str(e)}"}, status=500)


@csrf_exempt
def suggest_syllabus(request):
    """
    Suggest Subjects and Chapters based on Class Name using AI.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    if not client:
        return JsonResponse({"error": "Groq API not configured."}, status=500)

    class_name = request.POST.get("class_name", "").strip()
    if not class_name:
         return JsonResponse({"error": "Class name required"}, status=400)

    prompt = (
        f"Identify the standard subjects and list 3-5 key chapters/topics for each subject for {class_name} level (based on CBSE/NCERT curriculum).\n"
        f"Output MUST be a valid JSON object. Do NOT include markdown formatting.\n"
        f"Format: {{ 'subjects': [ {{ 'name': 'Mathematics', 'chapters': ['Algebra', 'Geometry'] }}, ... ] }}"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        
        raw_text = response.choices[0].message.content
        cleaned = clean_ai_text(raw_text)
        
        # JSON cleanup
        import json
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
            
        data = json.loads(cleaned.strip())
        return JsonResponse(data)
    except Exception as e:
        logger.exception("suggest_syllabus error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_student_report(request):
    """
    Endpoint to generate detailed student performance report.
    """
    from ..models import StudentProfile, StudentAnswer, ExamAnswer

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    if not client:
        return JsonResponse({"error": "Groq API not configured."}, status=500)

    student_id = request.POST.get("student_id")
    if not student_id:
        return JsonResponse({"error": "Student ID required"}, status=400)

    try:
        student_profile = StudentProfile.objects.select_related('user').get(user__id=student_id)
        
        assignments = StudentAnswer.objects.filter(student=student_profile).select_related('question').order_by('-submitted_at')[:10]
        exams = ExamAnswer.objects.filter(student=student_profile).select_related('question', 'exam').order_by('-id')[:10]

        data_summary = []
        
        for ans in assignments:
            q_desc = (ans.question.description or "")[:100]
            ans_text = (ans.answer_text or "")[:100]
            status = "Graded" if ans.remarks else "Pending"
            data_summary.append(f"- Assignment: {q_desc} -> Answer: {ans_text} [Status: {status}]")

        for ans in exams:
            q_text = (ans.question.text or "")[:100]
            ans_text = (ans.answer_text or "")[:100]
            marks = ans.marks_obtained
            total = ans.question.marks
            data_summary.append(f"- Exam '{ans.exam.title}': {q_text} -> Answer: {ans_text} [Marks: {marks}/{total}]")

        if not data_summary:
            return JsonResponse({"report": "<p>Not enough data to generate a report. The student has not submitted sufficient assignments or exams.</p>"})

        context_str = "\n".join(data_summary)

        prompt = (
            f"You are an academic advisor analyzing the performance of {student_profile.user.full_name}.\n"
            f"Based on the following recent records:\n{context_str}\n\n"
            f"Generate a Performance Report in HTML format (use <h3> for headings, <ul>/<li> for lists, <p> for paragraphs).\n"
            f"Sections to include:\n"
            f"1. Strengths (What are they doing well?)\n"
            f"2. Weaknesses (Where are errors occurring?)\n"
            f"3. Suggested Steps (Specific topics to review)\n\n"
            f"Keep the tone encouraging but constructive."
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        
        raw_text = response.choices[0].message.content
        
        cleaned = clean_ai_text(raw_text)
        if cleaned.startswith("```html"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
            
        return JsonResponse({"report": cleaned.strip()})

    except StudentProfile.DoesNotExist:
        return JsonResponse({"error": "Student profile not found."}, status=404)
    except Exception as e:
        logger.exception("generate_student_report error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)

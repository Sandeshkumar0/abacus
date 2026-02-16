
"""
AI and Groq-related utility functions for the dashboard app.
Handles AI-powered answer generation, query responses, and grading feedback.
Updated to use Groq (Llama 3) instead of OpenAI/Grok.
"""

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
import json
import ast
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
        f"- \"text\": The question string (no numbering).\n"
        f"- \"marks\": Integer suggested marks (e.g. 2 for Easy, 5 for Medium, 10 for Hard).\n"
        f"- \"type\": String 'Easy', 'Medium', or 'Hard'.\n"
        f"- \"latex\": (Optional) LaTeX string if math is involved, else empty string.\n"
        f"Example format: [{{\"text\": \"What is 5+5?\", \"marks\": 2, \"type\": \"Easy\", \"latex\": \"\"}}]"
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
        import ast
        
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
            # Fallback: try ast.literal_eval for Python-style lists/dicts (single quotes)
            try:
                questions_json = ast.literal_eval(cleaned_text)
            except (ValueError, SyntaxError) as e:
                logger.error(f"JSON/AST Parse Error: {e} | Text: {raw_text}")
                return JsonResponse({"error": "Failed to parse AI response."}, status=500)
            
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
        f"Format: {{ \"subjects\": [ {{ \"name\": \"Mathematics\", \"chapters\": [\"Algebra\", \"Geometry\"] }}, ... ] }}"
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
            
        try:
            data = json.loads(cleaned.strip())
            return JsonResponse(data)
        except json.JSONDecodeError:
            try:
                import ast
                data = ast.literal_eval(cleaned.strip())
                return JsonResponse(data)
            except Exception as e:
                logger.error(f"JSON/AST Parse Error in suggest_syllabus: {e} | Text: {raw_text}")
                return JsonResponse({"error": "Failed to parse AI response."}, status=500)
    except Exception as e:
        logger.exception("suggest_syllabus error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_student_report(request):
    """
    Endpoint to generate detailed student performance report.
    Returns structured HTML for the dashboard instead of AI text.
    """
    from ..models import StudentProfile
    
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    student_id = request.POST.get("student_id")
    if not student_id:
        return JsonResponse({"error": "Student ID required"}, status=400)

    try:
        from ..analytics import calculate_student_metrics, get_student_improvement_trend
        
        # 1. Get Quantitative Data
        metrics = calculate_student_metrics(student_id)
        if not metrics:
             return JsonResponse({"error": "Could not calculate metrics."}, status=500)

        # 2. Calculate Trend (Simple logic: compare last 3 avg vs previous 3 avg)
        trend_data = get_student_improvement_trend(student_id)
        trend_pct = 0
        if len(trend_data) >= 2:
            # Simple trend: Last accuracy - First accuracy in the window
            # Or better: Average of last half vs first half
            mid = len(trend_data) // 2
            recent = trend_data[mid:]
            older = trend_data[:mid]
            
            avg_recent = sum([x['accuracy'] for x in recent]) / len(recent)
            avg_older = sum([x['accuracy'] for x in older]) / len(older)
            trend_pct = int(avg_recent - avg_older)

        trend_sign = "↑" if trend_pct >= 0 else "↓"
        trend_color = "text-green-600" if trend_pct >= 0 else "text-red-600"
        
        # 3. Build HTML Report directly (Visual Dashboard)
        # Using Tailwind classes as per the project style
        
        # Helper to format list items
        def format_list(items, icon, color_class):
            if not items:
                return f"<li class='text-gray-500 italic'>None detected yet</li>"
            return "".join([f"<li class='mb-1'>{icon} {item}</li>" for item in items])

        overall_acc = int(metrics['overall_accuracy'])
        
        # Determine Progress Bar Color
        if overall_acc >= 75:
            bar_color = "bg-green-500"
        elif overall_acc >= 50:
            bar_color = "bg-yellow-500"
        else:
            bar_color = "bg-red-500"

        html_report = f"""
        <div class="performance-card font-sans">
            <h3 class="text-lg font-bold text-gray-800 mb-4 border-b pb-2">Performance Overview</h3>
            
            <!-- Overall Mastery -->
            <div class="mb-6">
                <div class="flex justify-between items-end mb-2">
                    <span class="text-sm font-semibold text-gray-600">Overall Mastery</span>
                    <span class="text-2xl font-bold text-gray-800">{overall_acc}%</span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-3">
                    <div class="{bar_color} h-3 rounded-full transition-all duration-500" style="width: {overall_acc}%"></div>
                </div>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <!-- Strong Areas -->
                <div class="bg-green-50 rounded-lg p-4 border border-green-100">
                    <h4 class="font-bold text-green-800 mb-2 flex items-center">
                        <span class="mr-2">💪</span> Strong In
                    </h4>
                    <ul class="text-sm text-green-700 list-none pl-0">
                        {format_list(metrics['strong_areas'], '✔', 'text-green-700')}
                    </ul>
                </div>
                
                <!-- Weak Areas -->
                <div class="bg-red-50 rounded-lg p-4 border border-red-100">
                    <h4 class="font-bold text-red-800 mb-2 flex items-center">
                        <span class="mr-2">🎯</span> Needs Practice
                    </h4>
                    <ul class="text-sm text-red-700 list-none pl-0">
                         {format_list(metrics['weak_areas'], '⚠', 'text-red-700')}
                    </ul>
                </div>
            </div>
            
            <!-- Trend -->
            <div class="mt-6 flex items-center justify-between bg-blue-50 p-4 rounded-lg border border-blue-100">
                <div>
                    <h4 class="font-bold text-blue-800 text-sm">Improvement Trend</h4>
                    <p class="text-xs text-blue-600">Based on recent activity</p>
                </div>
                <div class="text-xl font-bold {trend_color}">
                    {trend_sign} {abs(trend_pct)}% <span class="text-sm font-normal text-gray-600">this week</span>
                </div>
            </div>
        </div>
        """
        
        return JsonResponse({"report": html_report.strip()})

    except Exception as e:
        logger.exception("generate_student_report error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_class_report(request):
    """
    Endpoint to generate a Class/Group performance report for teachers.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    
    if not client:
        return JsonResponse({"error": "Groq API not configured."}, status=500)

    class_name = request.POST.get("class_name")
    group_id = request.POST.get("group_id")
    
    if not class_name and not group_id:
        return JsonResponse({"error": "Class Name or Group ID required"}, status=400)

    try:
        from ..analytics import calculate_group_metrics
        
        metrics = calculate_group_metrics(group_id=group_id, class_name=class_name)
        
        if not metrics:
            return JsonResponse({"error": "No data found for this class/group."}, status=404)
            
        # Build Context
        context_str = (
            f"Total Students: {metrics['total_students']}\n"
            f"Average Class Accuracy: {metrics['avg_class_accuracy']}%\n"
            f"Strong Topics: {', '.join(metrics['group_strong_areas'])}\n"
            f"Weak Topics: {', '.join(metrics['group_weak_areas'])}\n"
        )
        
        if metrics['at_risk_students']:
            names = [s['name'] for s in metrics['at_risk_students']]
            context_str += f"Students At Risk (<40%): {', '.join(names)}\n"
            
        if metrics['top_performers']:
            names = [s['name'] for s in metrics['top_performers']]
            context_str += f"Top Performers (>80%): {', '.join(names)}\n"

        target = class_name if class_name else f"Group {group_id}"
        
        prompt = (
            f"You are a senior academic coordinator advising a teacher regarding '{target}'.\n"
            f"Here is the Class Performance Data:\n{context_str}\n\n"
            f"Generate a Teacher's Strategy Report in HTML format (use <h3>, <ul>, <p>).\n"
            f"Sections to include:\n"
            f"1. **Class Overview**: General health of the class.\n"
            f"2. **Critical Gaps**: Discuss the weak topics and suggest specific remedial activities.\n"
            f"3. **Differentiation Strategy**:\n"
            f"   - How to support the 'At Risk' students.\n"
            f"   - How to challenge the 'Top Performers'.\n"
            f"4. **Action Plan**: 3 concrete steps for the next week.\n"
        )

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500
        )
        
        raw = response.choices[0].message.content
        return JsonResponse({"report": clean_ai_text(raw)})

    except Exception as e:
        logger.exception("generate_class_report error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_weak_topic_practice(request):
    """
    Generate practice questions specifically for weak subtopics.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    
    if not client:
        logger.error("Groq API client not initialized - check GROQ_API_KEY in .env")
        return JsonResponse({"error": "AI service not configured. Please contact administrator."}, status=500)

    try:
        data = json.loads(request.body)
        chapter_name = data.get("chapter_name")
        weak_subtopics = data.get("weak_subtopics", [])
        logger.info(f"Practice request: chapter={chapter_name}, subtopics={weak_subtopics}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        chapter_name = request.POST.get("chapter_name")
        weak_subtopics = request.POST.getlist("weak_subtopics[]")

    if not chapter_name or not weak_subtopics:
        logger.warning(f"Missing data: chapter={chapter_name}, subtopics={weak_subtopics}")
        return JsonResponse({"error": "Chapter and weak subtopics required."}, status=400)

    prompt = (
        f"You are an expert tutor. The student is weak in the following subtopics of '{chapter_name}': "
        f"{', '.join(weak_subtopics)}.\n"
        f"Create 5 practice questions focusing ONLY on these weak areas.\n"
        f"Output MUST be a valid JSON array of objects. Do NOT include markdown formatting.\n"
        f"Each object must have:\n"
        f"- \"text\": Question string.\n"
        f"- \"subtopic\": One of the weak subtopics this question targets.\n"
        f"- \"difficulty\": 'Medium' or 'Hard'.\n"
        f"- \"marks\": 5.\n"
        f"Format: [{{ \"text\": \"...\", \"subtopic\": \"...\", \"difficulty\": \"Medium\", \"marks\": 5 }}]"
    )

    try:
        logger.info("Calling Groq API for practice questions...")
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.7
        )
        
        raw_text = response.choices[0].message.content
        logger.info(f"Groq API response received: {raw_text[:200]}...")
        
        # Robust JSON parsing
        
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        cleaned_text = ""
        questions_json = []

        if json_match:
             cleaned_text = json_match.group(0)
        else:
             cleaned_text = clean_ai_text(raw_text)
             # Strip markdown
             if cleaned_text.startswith("```json"): cleaned_text = cleaned_text[7:]
             if cleaned_text.startswith("```"): cleaned_text = cleaned_text[3:]
             if cleaned_text.endswith("```"): cleaned_text = cleaned_text[:-3]

        try:
             questions_json = json.loads(cleaned_text.strip())
             logger.info(f"Successfully parsed {len(questions_json)} questions")
        except json.JSONDecodeError as je:
             logger.warning(f"JSON parse failed, trying ast.literal_eval: {je}")
             try:
                 questions_json = ast.literal_eval(cleaned_text.strip())
                 logger.info(f"Successfully parsed with ast: {len(questions_json)} questions")
             except Exception as e:
                 logger.error(f"JSON Parse Error (Weak Practice): {e} | Text: {raw_text}")
                 return JsonResponse({"error": "Failed to parse AI response. Please try again."}, status=500)
        
        return JsonResponse({"questions": questions_json})
        
    except Exception as e:
        logger.exception("generate_weak_topic_practice error: %s", e)
        return JsonResponse({"error": f"AI service error: {str(e)}"}, status=500)


@csrf_exempt
def analyze_student_performance(request):
    """
    Provide intelligent insights based on speed, accuracy, and difficulty curve.
    Used in Chapter Intelligence Panel.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    
    if not client:
        return JsonResponse({"error": "Groq API not configured."}, status=500)

    try:
        # Expecting JSON body with performance stats
        data = json.loads(request.body)
        chapter_name = data.get("chapter_name")
        overall_accuracy = data.get("overall_accuracy")
        strong_topics = data.get("strong_topics", [])
        weak_topics = data.get("weak_topics", [])
        avg_time = data.get("avg_time_per_question", "Unknown") # text like "45s"
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    prompt = (
        f"You are a smart educational AI. Analyze this student's performance in '{chapter_name}':\n"
        f"- Overall Accuracy: {overall_accuracy}%\n"
        f"- Strong Subtopics: {', '.join(strong_topics)}\n"
        f"- Weak Subtopics: {', '.join(weak_topics)}\n"
        f"- Avg Time/Q: {avg_time}\n\n"
        f"Provide a short, insightful 2-sentence analysis.\n"
        f"Example 1: 'You have a strong conceptual grasp of Factoring but struggle with application in Word Problems. Accuracy is good, but try to speed up.'\n"
        f"Example 2: 'You are answering quickly but making careless errors in Algebra. Slow down and double-check signs.'\n"
        f"Directly address the student (You...)."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7
        )
        
        insight = response.choices[0].message.content.strip()
        return JsonResponse({"insight": clean_ai_text(insight)})
        
    except Exception as e:
        logger.exception("analyze_student_performance error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


"""
AI and Groq-related utility functions for the dashboard app.
Handles AI-powered answer generation, query responses, and grading feedback.
Updated to use Groq (Llama 3) instead of OpenAI/Grok.
"""

from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
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

from ..models import Chapter, ExamAnswer, Query, StudentAnswer, Subject, TopicLearningCache

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


MATH_KEYWORDS = {
    "algebra", "calculus", "trigonometry", "geometry", "arithmetic",
    "number system", "probability", "statistics", "mensuration", "equation"
}


def filter_topics_for_subject(topics, chapter_subject):
    """Keep only subject-relevant topics for safer insights/questions."""
    if not topics:
        return []

    subject = (chapter_subject or "").strip().lower()
    cleaned = [str(t).strip() for t in topics if str(t).strip()]

    if "english" in subject:
        return [
            topic for topic in cleaned
            if not any(keyword in topic.lower() for keyword in MATH_KEYWORDS)
        ]
    return cleaned


def clean_ai_text(text: str) -> str:
    """Remove common markdown/heading artifacts from output."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = text.replace("##", "").replace("#", "")
    return text.strip()


def normalize_steps_and_answer(text: str) -> str:
    """
    Keep only:
    - Step 1..N lines
    - Final Answer line
    """
    if not text:
        return ""

    src_lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    step_lines = []
    final_answer = ""

    for line in src_lines:
        if re.match(r"^step\s*\d+[:.)\-\s]", line, flags=re.IGNORECASE):
            step_lines.append(re.sub(r"\s+", " ", line))
            continue
        if re.match(r"^final\s*answer[:.)\-\s]", line, flags=re.IGNORECASE):
            final_answer = re.sub(r"\s+", " ", line)

    # Fallback when model didn't format exactly.
    if not step_lines:
        chunks = [ln for ln in src_lines if not re.match(r"^final\s*answer", ln, flags=re.IGNORECASE)]
        for idx, chunk in enumerate(chunks[:6], start=1):
            step_lines.append(f"Step {idx}: {re.sub(r'\\s+', ' ', chunk)}")

    if not final_answer:
        # Try to infer from last non-step line, else keep explicit placeholder.
        candidate = ""
        for line in reversed(src_lines):
            if not re.match(r"^step\s*\d+", line, flags=re.IGNORECASE):
                candidate = line
                break
        final_answer = f"Final Answer: {candidate}" if candidate else "Final Answer: N/A"

    return "\n".join(step_lines + [final_answer]).strip()


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
        prompt = (
            "You are a subject expert.\n"
            "Solve the question and return ONLY this format:\n"
            "Step 1: ...\n"
            "Step 2: ...\n"
            "...\n"
            "Final Answer: ...\n"
            "No extra intro, no outro, no markdown.\n\n"
            f"Question:\n{question}"
        )
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
        cleaned = clean_ai_text(raw)
        return JsonResponse({"answer": normalize_steps_and_answer(cleaned)})
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
@login_required
def topic_learning_content(request):
    """
    Returns flashcards + practice questions for a chapter topic with DB caching.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    topic = (request.POST.get("topic") or "").strip()
    chapter_id = request.POST.get("chapter_id")
    language = (request.POST.get("language") or "en").strip() or "en"
    if not topic or not chapter_id:
        return JsonResponse({"error": "chapter_id and topic are required."}, status=400)

    try:
        chapter = Chapter.objects.get(id=chapter_id)
    except Chapter.DoesNotExist:
        return JsonResponse({"error": "Chapter not found."}, status=404)

    cached = TopicLearningCache.objects.filter(
        chapter=chapter,
        topic__iexact=topic,
        language=language,
    ).first()
    if cached:
        return JsonResponse(
            {
                "cached": True,
                "flashcards": cached.flashcards_json,
                "practice_questions": cached.practice_questions_json,
            }
        )

    flashcards = []
    practice_questions = []
    if client:
        prompt = (
            "Generate strict JSON for student learning.\n"
            f"Language: {language}\n"
            f"Chapter: {chapter.name}\n"
            f"Topic: {topic}\n"
            "Return ONLY a JSON object with keys:\n"
            "- flashcards: array of 5 to 10 objects with 'question' and 'answer'.\n"
            "- practice_questions: array of 5 objects with keys 'type' (MCQ/Short), 'question', 'options' (for MCQ only), and 'answer'."
        )
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1800,
                temperature=0.3,
            )
            raw_text = (response.choices[0].message.content or "").strip()
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            payload_text = json_match.group(0) if json_match else raw_text
            payload = json.loads(payload_text)
            flashcards = payload.get("flashcards", []) or []
            practice_questions = payload.get("practice_questions", []) or []
        except Exception as exc:
            logger.warning("topic_learning_content AI parse fallback used: %s", exc)

    if not flashcards:
        flashcards = [
            {"question": f"What is {topic}?", "answer": f"{topic} is a key concept in {chapter.name}."},
            {"question": f"Why is {topic} important?", "answer": f"It helps build strong fundamentals for {chapter.name}."},
            {"question": f"Where is {topic} used?", "answer": "It appears in examples, exercises, and applied problem solving."},
            {"question": f"What mistakes should be avoided in {topic}?", "answer": "Read definitions carefully and validate each step."},
            {"question": f"How to revise {topic} quickly?", "answer": "Use formula summaries, examples, and short quizzes."},
        ]
    if not practice_questions:
        practice_questions = [
            {"type": "MCQ", "question": f"Which statement best describes {topic}?", "options": ["A", "B", "C", "D"], "answer": "A"},
            {"type": "MCQ", "question": f"Choose the correct example of {topic}.", "options": ["Option 1", "Option 2", "Option 3", "Option 4"], "answer": "Option 1"},
            {"type": "Short", "question": f"Write two key points about {topic}.", "answer": "Student specific"},
            {"type": "Short", "question": f"Explain one application of {topic}.", "answer": "Student specific"},
            {"type": "MCQ", "question": f"What is the first step when solving a {topic} problem?", "options": ["Read data", "Guess", "Skip", "Memorize"], "answer": "Read data"},
        ]

    TopicLearningCache.objects.create(
        chapter=chapter,
        topic=topic,
        language=language,
        flashcards_json=flashcards,
        practice_questions_json=practice_questions,
    )
    return JsonResponse(
        {
            "cached": False,
            "flashcards": flashcards,
            "practice_questions": practice_questions,
        }
    )


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
    Suggest subjects/chapters based on selected class.
    Priority:
    1) Existing DB subjects (teacher's own subjects when logged in as teacher)
    2) AI topic suggestion for DB subjects that don't have chapters
    3) Full AI fallback when no DB subjects exist
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    class_name = request.POST.get("class_name", "").strip()
    if not class_name:
        return JsonResponse({"error": "Class name required"}, status=400)

    # Build class-level candidates (e.g. "Class 5", "5", "class 5")
    class_level_candidates = {class_name}
    class_digits = "".join(ch for ch in class_name if ch.isdigit())
    if class_digits:
        class_level_candidates.update({class_digits, f"Class {class_digits}", f"class {class_digits}"})

    subject_qs = Subject.objects.all()
    if request.user.is_authenticated and getattr(request.user, "is_teacher", False):
        subject_qs = subject_qs.filter(teacher__user=request.user)

    # Primary filter: exact class-level matches
    subject_qs = subject_qs.filter(class_level__in=class_level_candidates)
    db_subjects = list(subject_qs.prefetch_related("chapters").order_by("name"))

    # Relaxed fallback for messy stored class values, e.g. "Class 1-2"
    if not db_subjects and class_digits:
        relaxed_qs = Subject.objects.all()
        if request.user.is_authenticated and getattr(request.user, "is_teacher", False):
            relaxed_qs = relaxed_qs.filter(teacher__user=request.user)
        db_subjects = list(
            relaxed_qs.filter(
                djmodels.Q(class_level__icontains=class_digits) | djmodels.Q(class_level__iexact=class_name)
            ).prefetch_related("chapters").order_by("name")
        )

    if db_subjects:
        result_subjects = []
        needs_ai = []
        for sub in db_subjects:
            chapters = list(
                sub.chapters.order_by("chapter_number", "name").values_list("name", flat=True)
            )
            if not chapters:
                needs_ai.append(sub.name)
            result_subjects.append({"name": sub.name, "chapters": chapters[:8]})

        # Fill missing topics via AI for subjects with no chapters
        if needs_ai and client:
            prompt = (
                f"For {class_name}, return only JSON object with key 'subjects'.\n"
                f"Generate 3-5 chapter/topic names for each of these subjects: {', '.join(needs_ai)}.\n"
                "Format strictly: "
                "{\"subjects\": [{\"name\": \"Subject\", \"chapters\": [\"Topic 1\", \"Topic 2\"]}]}"
            )
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=700,
                    temperature=0.4,
                )
                raw_text = response.choices[0].message.content or ""
                cleaned = clean_ai_text(raw_text).strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                ai_payload = json.loads(cleaned.strip())
                ai_map = {
                    (item.get("name") or "").strip().lower(): (item.get("chapters") or [])
                    for item in (ai_payload.get("subjects") or [])
                }
                for item in result_subjects:
                    if not item["chapters"]:
                        item["chapters"] = ai_map.get(item["name"].lower(), [])[:8]
            except Exception as exc:
                logger.warning("suggest_syllabus db+ai fallback parse failed: %s", exc)

        return JsonResponse({"subjects": result_subjects, "source": "db"})

    # No DB subjects found: fallback to AI-generated syllabus list
    if not client:
        return JsonResponse({"subjects": [], "source": "none", "error": "No DB subjects and AI not configured."})

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
            data["source"] = "ai"
            return JsonResponse(data)
        except json.JSONDecodeError:
            try:
                import ast
                data = ast.literal_eval(cleaned.strip())
                if isinstance(data, dict):
                    data["source"] = "ai"
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
        chapter_id = data.get("chapter_id")
        chapter_subject = data.get("chapter_subject", "")
        weak_subtopics = data.get("weak_subtopics", [])
        weak_subtopics = filter_topics_for_subject(weak_subtopics, chapter_subject)
        logger.info(f"Practice request: chapter={chapter_name}, subtopics={weak_subtopics}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        chapter_name = request.POST.get("chapter_name")
        chapter_id = request.POST.get("chapter_id")
        chapter_subject = request.POST.get("chapter_subject", "")
        weak_subtopics = request.POST.getlist("weak_subtopics[]")
        weak_subtopics = filter_topics_for_subject(weak_subtopics, chapter_subject)

    if not chapter_name or not weak_subtopics:
        logger.warning(f"Missing data: chapter={chapter_name}, subtopics={weak_subtopics}")
        return JsonResponse({"error": "Chapter and weak subtopics required."}, status=400)

    prompt = (
        f"You are an expert tutor. The student is weak in the following subtopics of '{chapter_name}': "
        f"{', '.join(weak_subtopics)}.\n"
        f"Subject: {chapter_subject or 'Unknown'}.\n"
        f"Create 5 practice questions focusing ONLY on these weak areas.\n"
        f"Do not generate any question from another subject domain.\n"
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
        
        # Persist generated questions so refresh does not reset practice set.
        persisted_questions = []
        try:
            from django.utils import timezone
            from accounts.models import StudentProfile
            from ..models import Question, Chapter
            from accounts.models import TeacherProfile

            chapter_obj = None
            if chapter_id:
                chapter_obj = Chapter.objects.filter(id=chapter_id).select_related('subject').first()

            student_profile = None
            if request.user.is_authenticated:
                student_profile = StudentProfile.objects.filter(user=request.user).first()

            teacher_profile = TeacherProfile.objects.first()
            teacher_user = request.user if request.user.is_authenticated else (teacher_profile.user if teacher_profile else None)

            if chapter_obj and student_profile and teacher_profile and teacher_user:
                from ..models import StudentAnswer
                for q in questions_json:
                    q_text = (q.get("text") or "").strip()
                    q_subtopic = (q.get("subtopic") or "General").strip() or "General"
                    q_difficulty = (q.get("difficulty") or "Medium").strip() or "Medium"
                    q_marks = int(q.get("marks") or 5)
                    if not q_text:
                        continue

                    question = Question.objects.create(
                        teacher=teacher_profile,
                        teacher_name=teacher_user,
                        description=q_text,
                        due_date=timezone.now(),
                        chapter=chapter_obj,
                        subject=chapter_obj.subject,
                        subtopic=q_subtopic,
                        concept_tags=q_subtopic,
                        is_practice=True,
                        max_marks=q_marks,
                        difficulty=q_difficulty if q_difficulty in {"Easy", "Medium", "Hard"} else "Medium",
                    )

                    StudentAnswer.objects.get_or_create(
                        student=student_profile,
                        question=question,
                        defaults={
                            "student_name": request.user,
                            "student_roll": student_profile,
                            "answer_text": "",
                            "marks_obtained": None,
                        },
                    )

                    persisted_questions.append({
                        "id": question.id,
                        "text": question.description,
                        "subtopic": question.subtopic or "General",
                        "difficulty": question.difficulty,
                        "marks": question.max_marks,
                    })
        except Exception as persist_err:
            logger.warning("Practice persistence failed; returning transient questions. Error: %s", persist_err)

        return JsonResponse({"questions": persisted_questions or questions_json})
        
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
        chapter_subject = data.get("chapter_subject", "")
        overall_accuracy = data.get("overall_accuracy")
        strong_topics = data.get("strong_topics", [])
        weak_topics = data.get("weak_topics", [])
        strong_topics = filter_topics_for_subject(strong_topics, chapter_subject)
        weak_topics = filter_topics_for_subject(weak_topics, chapter_subject)
        avg_time = data.get("avg_time_per_question", "Unknown") # text like "45s"
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    prompt = (
        f"You are a smart educational AI. Analyze this student's performance in '{chapter_name}':\n"
        f"- Subject: {chapter_subject or 'Unknown'}\n"
        f"- Overall Accuracy: {overall_accuracy}%\n"
        f"- Strong Subtopics: {', '.join(strong_topics)}\n"
        f"- Weak Subtopics: {', '.join(weak_topics)}\n"
        f"- Avg Time/Q: {avg_time}\n\n"
        f"Provide a short, insightful 2-sentence analysis.\n"
        f"Do not mention topics from other subjects.\n"
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

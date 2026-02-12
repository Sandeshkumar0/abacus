"""
AI and Gemini-related utility functions for the dashboard app.
Handles AI-powered answer generation, query responses, and grading feedback.
"""

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import google.generativeai as genai
import re
import os
import mimetypes
import logging
import io
from django.db import models as djmodels
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from dotenv import load_dotenv

from ..models import StudentAnswer, Query, ExamAnswer

logger = logging.getLogger(__name__)

# Load environment variables and configure Gemini
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Only configure if API key is available
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("⚠️ GEMINI_API_KEY not configured. AI features will not work. Get your API key from: https://makersuite.google.com/app/apikey")


def extract_text_from_response(response):
    """Safely extract main text from Gemini response regardless of format."""
    if not response:
        return ""

    # Try the direct .text property (most reliable for Gemini 1.5)
    if hasattr(response, "text") and response.text:
        return response.text

    # Try candidates → content → parts
    try:
        for cand in getattr(response, "candidates", []):
            if hasattr(cand, "content"):
                # Sometimes content has .parts
                if hasattr(cand.content, "parts"):
                    texts = [p.text for p in cand.content.parts if hasattr(p, "text")]
                    if texts:
                        return "\n".join(texts)
                # Sometimes it's just a list
                if isinstance(cand.content, list):
                    texts = [c.text for c in cand.content if hasattr(c, "text")]
                    if texts:
                        return "\n".join(texts)
    except Exception:
        pass

    return str(response)


def clean_ai_text(text: str) -> str:
    """Remove common markdown/heading artifacts from Gemini output."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = text.replace("##", "").replace("#", "")
    return text.strip()


def collect_attachments_from_instance(instance):
    """
    Inspect a Django model instance and return a list of attachments (bytes + metadata)
    for any FileField/ImageField the instance owns.
    Returns: list of dicts: [{'name': ..., 'mime_type': ..., 'data': b'...'}, ...]
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
                    attachments.append({
                        "name": filename,
                        "mime_type": mime_type,
                        "data": data
                    })
                    file_field.close()
                except Exception as e:
                    logger.exception("Failed reading file field %s on %s: %s", field.name, instance, e)
                    # continue reading other fields
    except Exception as e:
        logger.exception("collect_attachments_from_instance error: %s", e)
    return attachments


def build_gemini_parts(text_prompt: str, attachments: list):
    """
    Build input 'parts' for genai.generate_content().
    `text_prompt` - the primary textual prompt (string)
    `attachments` - list of dicts {name,mime_type,data}
    Returns list suitable for model.generate_content(...)
    """
    parts = []
    if text_prompt:
        parts.append({"text": text_prompt})
    for att in attachments or []:
        # Gemini client expects binary bytes in 'data' and a mime_type
        parts.append({
            "mime_type": att.get("mime_type", "application/octet-stream"),
            "data": att.get("data")
        })
    return parts


@csrf_exempt
def generate_answer_assign(request):
    """
    Endpoint for assign_question.html → returns {"answer": "..."}.
    Attachments are not required here (assignments typically text-based),
    but we accept them if they are provided on POST (e.g., teacher attaches a diagram).
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    question = (request.POST.get("question") or "").strip()
    if not question:
        return JsonResponse({"error": "No question provided."}, status=400)

    try:
        prompt = f"You are a subject expert. Create a clear, step-by-step solution for this assignment question:\n\n{question}"
        # If teacher uploaded attachments in the form (rare for this view), include them:
        attachments = []
        # Check if front-end sent any files under 'attachments' (FormData)
        if request.FILES:
            for f in request.FILES.getlist("attachments"):
                try:
                    data = b"".join(chunk for chunk in f.chunks())
                    mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                    attachments.append({"name": f.name, "mime_type": mime, "data": data})
                except Exception:
                    logger.exception("Failed to read uploaded file %s", f.name)

        parts = build_gemini_parts(prompt, attachments)
        model = genai.GenerativeModel("models/gemini-pro")
        response = model.generate_content(parts)

        # robust extraction of text from response
        if response and getattr(response, "candidates", None):
            cand = response.candidates[0]
            # try common places
            raw = ""
            try:
                raw = extract_text_from_response(response)
            except Exception:
                try:
                    raw = cand.content.parts[0].text
                except Exception:
                    raw = str(cand)
            return JsonResponse({"answer": clean_ai_text(raw)})
        return JsonResponse({"error": "No answer generated."}, status=500)
    except Exception as e:
        logger.exception("generate_answer_assign error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_answer_query(request):
    """
    Endpoint for respond_query.html → returns {"answer": "..."}.
    Accepts:
      - question (text) OR
      - query_id (if provided, we fetch Query object and include its saved attachments)
    It sends original file bytes to Gemini (not a link).
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    question_text = (request.POST.get("question") or "").strip()
    query_id = request.POST.get("query_id") or request.POST.get("id")

    attachments = []
    # If query_id provided, try to pick files from Query model instance
    if query_id:
        try:
            q_obj = Query.objects.get(id=query_id)
            if not question_text:
                # prefer text from DB if not provided
                question_text = q_obj.query_text or question_text
            attachments = collect_attachments_from_instance(q_obj)
        except Query.DoesNotExist:
            logger.warning("Query id %s not found", query_id)

    # If front-end uploaded files in this POST (unlikely here), include them:
    if request.FILES:
        for f in request.FILES.getlist("attachments"):
            try:
                data = b"".join(chunk for chunk in f.chunks())
                mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                attachments.append({"name": f.name, "mime_type": mime, "data": data})
            except Exception:
                logger.exception("Failed to read uploaded file %s", f.name)

    if not question_text and not attachments:
        return JsonResponse({"error": "No query text or attachments provided."}, status=400)

    try:
        prompt = f"You are a teacher. Respond to this student query politely, explain step-by-step, and clear the student's doubt:\n\n{question_text}"
        parts = build_gemini_parts(prompt, attachments)
        model = genai.GenerativeModel("models/gemini-pro")
        response = model.generate_content(parts)

        if response and getattr(response, "candidates", None):
            cand = response.candidates[0]
            raw = ""
            try:
                raw = extract_text_from_response(response)
            except Exception:
                try:
                    raw = cand.content.parts[0].text
                except Exception:
                    raw = str(cand)
            return JsonResponse({"answer": clean_ai_text(raw)})
        return JsonResponse({"error": "No answer generated."}, status=500)
    except Exception as e:
        logger.exception("generate_answer_query error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def generate_remark_feedback(request):
    """
    Endpoint for remarks.html → returns {"feedback": "..."}.
    Supports both StudentAnswer and ExamAnswer. The frontend sends:
      - answer_id
      - answer_type ("student" or "exam")
    If frontend doesn't send question/answer text, the function will read from DB.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    answer_id = request.POST.get("answer_id") or request.POST.get("id")
    answer_type = (request.POST.get("answer_type") or "").lower()
    question_text = (request.POST.get("question") or "").strip()
    student_answer_text = (request.POST.get("answer") or request.POST.get("student_answer") or "").strip()

    attachments = []
    instance = None

    # Load the correct model instance
    if answer_id:
        if answer_type == "exam":
            try:
                instance = ExamAnswer.objects.select_related('question', 'exam', 'student_name').get(id=answer_id)
            except ExamAnswer.DoesNotExist:
                instance = None
        else:
            # try StudentAnswer first
            try:
                instance = StudentAnswer.objects.select_related('question', 'student_name').get(id=answer_id)
            except StudentAnswer.DoesNotExist:
                instance = None

    # If instance found, fill missing fields and collect attachments
    if instance:
        try:
            # Question text
            if not question_text:
                # StudentAnswer.question.description vs ExamAnswer.question.text
                q = getattr(instance, 'question', None)
                if q:
                    # different models: Question (description) vs ExamQuestion (text)
                    question_text = getattr(q, 'description', None) or getattr(q, 'text', '') or question_text

            # Student answer text
            if not student_answer_text:
                student_answer_text = getattr(instance, 'answer_text', '') or student_answer_text

            # attachments (files on the answer instance)
            attachments = collect_attachments_from_instance(instance)
        except Exception:
            # continue; server will still work with available text
            logger.exception("Error extracting from instance in generate_remark_feedback")

    # include any uploaded files in this POST
    if request.FILES:
        for f in request.FILES.getlist("attachments"):
            try:
                data = b"".join(chunk for chunk in f.chunks())
                mime = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                attachments.append({"name": f.name, "mime_type": mime, "data": data})
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
        parts = build_gemini_parts(base_prompt, attachments)
        model = genai.GenerativeModel("models/gemini-pro")
        response = model.generate_content(parts)

        if response:
            raw = extract_text_from_response(response)
            return JsonResponse({"feedback": clean_ai_text(raw)})
        return JsonResponse({"error": "No remark generated."}, status=500)
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

        # Custom styles
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

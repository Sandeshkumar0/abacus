from django.shortcuts import render,redirect
from django.http import HttpResponse
from accounts.models import TeacherProfile, StudentProfile
from django.contrib.auth.decorators import login_required
import os
import requests
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from dotenv import load_dotenv
import tempfile
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from django.db import models
from .models import StudentAnswer, Query, ExamAnswer



def student_dashboard(request):
    return render(request, 'student/student_dashboard.html')

from django.http import JsonResponse
from .models import StudentAnswer, Question
from accounts.models import StudentProfile

from django.views.decorators.csrf import csrf_exempt
import logging
logger = logging.getLogger(__name__)
@login_required
def submit_answer(request):
    if request.method == 'POST':
        question_id = request.POST.get('question_id')
        answer_text = request.POST.get('answer')
        answer_file = request.FILES.get('answer_file')  # ✅ new

        question = Question.objects.get(id=question_id)
        student_profile = StudentProfile.objects.get(user=request.user)

        StudentAnswer.objects.update_or_create(
            student=student_profile,
            student_name=request.user,
            student_roll=student_profile,
            question=question,
            defaults={
                'answer_text': answer_text,
                'answer_file': answer_file  # ✅ save file
            }
        )
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)



from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from django.http import FileResponse
import io
import urllib.parse
import requests
from PIL import Image

@login_required
def download_answer_pdf(request, question_id):
    question = Question.objects.get(id=question_id)
    student_profile = StudentProfile.objects.get(user=request.user)

    # This should match how you save the answer
    answer = StudentAnswer.objects.filter(student=student_profile, question=question).first()


    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    # Header
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, f"Question {question.id}")
    y -= 30

    # Question text
    p.setFont("Helvetica", 12)
    text = question.description.split("LaTeX Equation:")[0].strip()
    for line in text.split('\n'):
        p.drawString(50, y, line)
        y -= 20

    # If equation present
    if "LaTeX Equation:" in question.description:
        latex = question.description.split("LaTeX Equation:")[1].strip()
        latex_url = f"https://latex.codecogs.com/png.image?\\dpi{{150}} {urllib.parse.quote(latex)}"
        img_data = requests.get(latex_url).content

        with open("temp_eq.png", "wb") as f:
            f.write(img_data)

        img = Image.open("temp_eq.png")
        img_width, img_height = img.size

        max_width = 60  # ✅ Reduced to zoom out
        scale = max_width / img_width
        new_width = max_width
        new_height = img_height * scale

        y -= new_height + 10
        p.drawInlineImage("temp_eq.png", 50, y, width=new_width, height=new_height)
        y -= 20

    # Answer Section
    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "Answer:")
    y -= 30

    if answer and answer.answer_text:
        p.setFont("Helvetica", 12)
        for line in answer.answer_text.split('\n'):
            if y < 100:  # new page if space low
                p.showPage()
                y = height - 50
            p.drawString(50, y, line)
            y -= 20
    else:
        p.setFont("Helvetica-Oblique", 12)
        p.drawString(50, y, "No answer submitted.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"Answer_Q{question.id}.pdf")


from .models import Question
from accounts.models import StudentProfile
from django.contrib.auth.decorators import login_required

@login_required
def student_assign(request):
    student_profile = StudentProfile.objects.get(user=request.user)
    all_questions = Question.objects.all().order_by('created_at')
    answered_q_ids = StudentAnswer.objects.filter(student=student_profile).values_list('question_id', flat=True)
    unanswered_questions = all_questions.exclude(id__in=answered_q_ids)

    questions = []
    for q in unanswered_questions:
        desc = q.description
        if "LaTeX Equation:" in desc:
            parts = desc.split("LaTeX Equation:")
            question_text = parts[0].strip()
            latex = parts[1].strip()
        else:
            question_text = desc.strip()
            latex = ""
        questions.append({
            'id': q.id,
            'question_text': question_text,
            'latex': latex,
            'due_date': q.due_date,
            'max_marks': q.max_marks,
            'is_exam': q.is_exam,
            'file': q.image.url if q.image else None   # ✅ NEW
        })


    completed_count = StudentAnswer.objects.filter(student=student_profile).count()
    pending_count = unanswered_questions.count()

    return render(request, 'student/view_assigned_questions.html', {
        'questions': questions,
        'completed_count': completed_count,
        'pending_count': pending_count,
    })



from django.contrib.auth.decorators import login_required
from accounts.models import StudentProfile

@login_required
def student_profile(request):
    student = StudentProfile.objects.get(user=request.user)
    return render(request, 'student/profile.html', {'student': student})

from .models import Query
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from .models import Query
from django.db.models import Count, Avg
from django.utils.timezone import now, timedelta

@login_required
def raise_query(request):
    student_profile = StudentProfile.objects.get(user=request.user)

    if request.method == 'POST':
        query_text = request.POST.get('query_text')
        query_file = request.FILES.get('query_file')

        Query.objects.create(
            student=student_profile,
            student_name=request.user,
            student_roll=student_profile,
            query_text=query_text,
            query_image=query_file
        )
        return redirect('raise_query')

    # ---------- STATS CALCULATION ----------
    total_queries = Query.objects.filter(student=student_profile).count()
    resolved_queries = Query.objects.filter(student=student_profile).exclude(response="").count()
    unresolved_queries = total_queries - resolved_queries

    # Resolution rate
    resolution_rate = int((resolved_queries / total_queries) * 100) if total_queries > 0 else 0

    # Team utilization (example: avg queries per teacher this week)
    one_week_ago = now() - timedelta(days=7)
    utilization = Query.objects.filter(submitted_at__gte=one_week_ago).values('responded_by').annotate(total=Count('id'))
    total_teachers = TeacherProfile.objects.count()
    total_assignments = sum(entry['total'] for entry in utilization)
    team_utilization = int((total_assignments / (total_teachers or 1)) * 100)

    # Avg. response time (for resolved queries)
    from django.db.models import F, ExpressionWrapper, DurationField
    avg_response_qs = Query.objects.filter(response__isnull=False).annotate(
        response_time=ExpressionWrapper(F('responded_by__user__date_joined') - F('submitted_at'), output_field=DurationField())
    ).aggregate(avg_time=Avg('response_time'))

    avg_response_days = round(avg_response_qs['avg_time'].days if avg_response_qs['avg_time'] else 0)

    context = {
        'active_queries': unresolved_queries,
        'resolution_rate': resolution_rate,
        'team_utilization': team_utilization,
        'avg_response_days': avg_response_days,
    }

    return render(request, 'student/raise_query.html', context)


@login_required
def view_remarks(request):
    student = StudentProfile.objects.get(user=request.user)

    # Get all submitted answers for this student
    student_answers_raw = StudentAnswer.objects.filter(student=student).select_related('question')

    student_answers = []
    for ans in student_answers_raw:
        desc = ans.question.description
        if "LaTeX Equation:" in desc:
            parts = desc.split("LaTeX Equation:")
            question_text = parts[0].strip()
            latex = parts[1].strip()
        else:
            question_text = desc.strip()
            latex = ""
        student_answers.append({
            'question_number': ans.question.id,
            'question_text': question_text,
            'latex': latex,
            'answer_text': ans.answer_text,
            'answer_file': ans.answer_file.url if ans.answer_file else None,  # ✅ NEW
            'question_file': ans.question.file.url if ans.question.file else None,
            'remarks': ans.remarks,
            'teacher_name': ans.question.teacher_name.get_full_name() if ans.question.teacher_name else None
        })


    total_answers = len(student_answers)
    graded_count = sum(1 for ans in student_answers if ans['remarks'])
    pending_review = total_answers - graded_count

    context = {
        'student_answers': student_answers,
        'total_answers': total_answers,
        'graded_count': graded_count,
        'pending_review': pending_review,
    }

    return render(request, 'student/view_remarks.html', context)


@login_required(login_url='teacher_login')
def teacher_dashboard(request):
    # Check if user is authenticated and is a teacher
    if not request.user.is_authenticated:
        return redirect('teacher_login')
    if not request.user.is_teacher:
        return redirect('teacher_login')
    return render(request, 'teacher/teacher_dashboard.html')

from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Exam, ExamQuestion, ExamAnswer

@login_required
def get_exam_questions(request, exam_id):
    student_profile = StudentProfile.objects.get(user=request.user)
    exam = get_object_or_404(Exam, id=exam_id)

    # Prevent showing if already attempted
    if ExamAnswer.objects.filter(exam=exam, student=student_profile).exists():
        return JsonResponse({"status": "completed"})

    questions = []
    for q in exam.questions.all():
        questions.append({
            "id": q.id,
            "question_text": q.text,
            "latex": q.latex,
            "marks": q.marks,
        })

    return JsonResponse({"status": "ok", "exam": exam.title, "questions": questions})

@login_required
def attempt_exam(request, exam_id):
    student_profile = StudentProfile.objects.get(user=request.user)
    exam = get_object_or_404(Exam, id=exam_id)

    if ExamAnswer.objects.filter(exam=exam, student=student_profile).exists():
        return redirect("give_test")

    if request.method == "POST":
        for q in exam.questions.all():
            answer_text = request.POST.get(f"answer_{q.id}", "").strip()
            answer_file = request.FILES.get(f"answer_file_{q.id}")  # ✅ new

            ExamAnswer.objects.create(
                exam=exam,
                student=student_profile,
                student_name=request.user,
                student_roll=student_profile,
                question=q,
                answer_text=answer_text,
                answer_file=answer_file,  # ✅ save file
                marks_obtained=0
            )
        return redirect("give_test")

    context = {"exam": exam, "questions": exam.questions.all()}
    return render(request, "student/attempt_exam.html", context)


@login_required
def download_exam_answer_pdf(request, exam_id):
    """
    Generate a PDF for all answers of the logged-in student for a specific exam.
    Includes LaTeX equations (rendered as images).
    """
    exam = get_object_or_404(Exam, id=exam_id)
    student_profile = StudentProfile.objects.get(user=request.user)
    answers = ExamAnswer.objects.filter(exam=exam, student=student_profile)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    # Exam Header
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, f"Exam: {exam.title}")
    y -= 40

    for idx, ans in enumerate(answers, start=1):
        q = ans.question

        # Question Heading
        p.setFont("Helvetica-Bold", 13)
        p.drawString(50, y, f"Q{idx}. {q.text}")
        y -= 25

        # Render LaTeX if present
        if q.latex:
            latex_url = f"https://latex.codecogs.com/png.image?\\dpi{{150}} {urllib.parse.quote(q.latex)}"
            img_data = requests.get(latex_url).content
            with open("temp_eq.png", "wb") as f:
                f.write(img_data)

            img = Image.open("temp_eq.png")
            img_width, img_height = img.size
            max_width = 200
            scale = max_width / img_width
            new_width = max_width
            new_height = img_height * scale

            y -= new_height + 10
            p.drawInlineImage("temp_eq.png", 50, y, width=new_width, height=new_height)
            y -= 20

        # Answer text
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, y, "Answer:")
        y -= 20

        if ans.answer_text:
            p.setFont("Helvetica", 11)
            for line in ans.answer_text.split("\n"):
                if y < 100:  # Add new page if space runs out
                    p.showPage()
                    y = height - 50
                p.drawString(60, y, line)
                y -= 18
        else:
            p.setFont("Helvetica-Oblique", 11)
            p.drawString(60, y, "No answer submitted.")
            y -= 20

        y -= 30

        if y < 100:  # Avoid overlap, move to new page
            p.showPage()
            y = height - 50

    p.showPage()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"Exam_{exam.id}_Answers.pdf")



from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from .models import Exam, ExamAnswer

@login_required
def give_test(request):
    student_profile = request.user.studentprofile  

    # Completed exams (where student has answers)
    completed_exams = Exam.objects.filter(
        answers__student=student_profile
    ).distinct()

    for exam in completed_exams:
        # Attach only this student's answers
        exam.student_answers = ExamAnswer.objects.filter(
            exam=exam,
            student=student_profile
        ).select_related("question")

        # Calculate total obtained marks
        exam.obtained = exam.student_answers.aggregate(
            total=Sum("marks_obtained")
        )["total"] or 0

    # New exams (not yet attempted)
    new_exams = Exam.objects.exclude(
        answers__student=student_profile
    )

    return render(request, "student/give_test.html", {
        "completed_exams": completed_exams,
        "new_exams": new_exams,
    })



from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from .models import Question
from accounts.models import TeacherProfile
from datetime import datetime

@csrf_exempt
@login_required
def assign_questions(request):
    if request.method == 'POST':
        description = request.POST.get('description', '').strip()
        latex_equation = request.POST.get('latex_equation', '').strip()
        max_marks = int(request.POST.get('max_marks', 0))
        is_exam = request.POST.get('is_test') in ['true', 'on', '1']
        due_date_str = request.POST.get('due_date')
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                due_date = timezone.now()

        teacher = TeacherProfile.objects.get(user=request.user)

        # ✅ handle uploaded file
        uploaded_file = request.FILES.get('image')

        full_question = description
        if latex_equation:
            full_question += f"\n\nLaTeX Equation:\n{latex_equation}"

        Question.objects.create(
            teacher=teacher,
            teacher_name=request.user,
            description=full_question,
            due_date=due_date,
            is_exam=is_exam,
            max_marks=max_marks,
            image=uploaded_file   # ✅ save file
        )

        return redirect('assign_questions')

    return render(request, 'teacher/assign_questions.html')



from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime
from .models import Exam, ExamQuestion

@login_required
@csrf_exempt
def take_test(request):
    if request.method == "POST":
        exam_heading = request.POST.get("examHeading")
        due_date = request.POST.get("dueDate")
        total_marks = request.POST.get("totalMarks")
        questions_data = request.POST.getlist("questions[]")

        teacher = TeacherProfile.objects.get(user=request.user)
        exam = Exam.objects.create(
            teacher=teacher,
            teacher_name=request.user,
            title=exam_heading,
            due_date=parse_datetime(due_date),
            total_marks=total_marks,
        )

        import json
        for i, q in enumerate(questions_data):
            q_obj = json.loads(q)
            q_file = request.FILES.get(f"question_file_{i}")  # ✅ new
            ExamQuestion.objects.create(
                exam=exam,
                text=q_obj.get("text", ""),
                latex=q_obj.get("latex", ""),
                marks=q_obj.get("marks", 0),
                file=q_file
            )

        return JsonResponse({"status": "success", "exam_id": exam.id})
    return render(request, "teacher/take_test.html")

import json

@csrf_exempt
@login_required
def create_exam(request):
    if request.method == "POST":
        exam_heading = request.POST.get("examHeading")
        due_date_str = request.POST.get("dueDate")
        total_marks = request.POST.get("totalMarks")

        from django.utils.timezone import make_aware
        from datetime import datetime
        due_date = make_aware(datetime.strptime(due_date_str, "%Y-%m-%d %H:%M"))

        # Get teacher (both profile and user)
        teacher_profile = request.user.teacherprofile   # TeacherProfile instance
        teacher_user = request.user                     # CustomUser instance

        # ✅ assign both fields correctly
        exam = Exam.objects.create(
            teacher=teacher_profile,
            teacher_name=teacher_user,
            title=exam_heading,
            due_date=due_date,
            total_marks=total_marks,
        )

        # Save questions
        import json
        questions_data = request.POST.getlist("questions[]")
        for idx, q_json in enumerate(questions_data):
            q = json.loads(q_json)
            uploaded_file = request.FILES.get(f"question_file_{idx}")

            ExamQuestion.objects.create(
                exam=exam,
                text=q["text"],
                latex=q.get("latex", ""),
                marks=q["marks"],
                file=uploaded_file if uploaded_file else None,
            )

        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "failed"})




def teacher_profile(request):
    teacher = TeacherProfile.objects.get(user=request.user)
    return render(request, 'teacher/profile.html', {'teacher': teacher})

import os
import tempfile
import re
from django.http import FileResponse
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from dotenv import load_dotenv
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Gemini
import google.generativeai as genai

# Video transcript + fallback
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import yt_dlp
import whisper

# ---------------- Load env ----------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

GEMINI_MODEL = "gemini-1.5-flash"   # stick to flash

# ---------------- Text Cleaner ----------------
def clean_notes_text(text: str) -> str:
    """
    Remove markdown symbols (*, **) and extra formatting from Gemini output.
    """
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # remove **bold**
    text = re.sub(r"\*(.*?)\*", r"\1", text)      # remove *italic*
    text = text.replace("##", "").replace("#", "") # remove headings
    return text.strip()

# ---------------- Gemini Query ----------------
def query_gemini(prompt: str) -> str:
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)

        if response and response.candidates:
            return clean_notes_text(response.candidates[0].content.parts[0].text)
        else:
            return "⚠️ No response generated from Gemini."
    except Exception as e:
        print("Gemini error:", str(e))
        return f"⚠️ Error generating notes: {str(e)}"

# ---------------- Transcript Utils ----------------
def extract_youtube_id(url: str) -> str:
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None

def get_transcript_from_youtube(video_url: str) -> str:
    """
    Try to fetch transcript using youtube-transcript-api (fastest).
    """
    video_id = extract_youtube_id(video_url)
    if not video_id:
        return None
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        return " ".join([entry["text"] for entry in transcript])
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception as e:
        print("YouTube transcript error:", str(e))
        return None

def transcribe_with_whisper(video_url: str) -> str:
    """
    Download audio and transcribe with Whisper (fallback, slower).
    """
    tmp_dir = tempfile.gettempdir()
    filename = None
    error = None

    # Try audio-first formats
    for fmt in ["bestaudio/best", "best"]:
        ydl_opts = {
            "format": fmt,
            "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",
            }],
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                if not info:
                    continue
                filename = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp3"
                break  # success, stop trying
        except Exception as e:
            error = str(e)
            continue

    if not filename or not os.path.exists(filename):
        raise Exception(f"❌ yt_dlp failed to fetch audio. Last error: {error}")

    # Whisper transcription
    model = whisper.load_model("tiny")
    result = model.transcribe(filename, fp16=False)
    return result["text"]

def get_transcript(video_url: str) -> str:
    """
    Main: Try YouTube captions, else fallback to Whisper.
    """
    transcript = None
    if "youtube.com" in video_url or "youtu.be" in video_url:
        transcript = get_transcript_from_youtube(video_url)
    if not transcript:
        transcript = transcribe_with_whisper(video_url)
    return transcript

# ---------------- PDF Formatter ----------------
def format_notes_to_pdf(notes_text, buffer):
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = styles["Title"]
    heading1 = ParagraphStyle("Heading1", parent=styles["Heading1"], fontSize=14, spaceAfter=10, spaceBefore=10, bold=True)
    heading2 = ParagraphStyle("Heading2", parent=styles["Heading2"], fontSize=12, spaceAfter=6, spaceBefore=6, bold=True)
    heading3 = ParagraphStyle("Heading3", parent=styles["Heading3"], fontSize=11, spaceAfter=4, spaceBefore=4, bold=True)
    bullet_style = ParagraphStyle("Bullet", parent=styles["Normal"], leftIndent=20, bulletIndent=10, spaceAfter=4)
    normal_style = styles["Normal"]

    story = []
    story.append(Paragraph("Lecture Notes", title_style))
    story.append(Spacer(1, 20))

    for line in notes_text.split("\n"):
        text = line.strip()
        if not text:
            continue

        if re.match(r"^(lecture title|heading)[:\- ]", text.lower()):
            story.append(Paragraph(re.sub(r"^(lecture title|heading)[:\- ]", "", text, flags=re.I), heading1))
        elif re.match(r"^(subheading|##)[:\- ]", text.lower()):
            story.append(Paragraph(re.sub(r"^(subheading|##)[:\- ]", "", text, flags=re.I), heading2))
        elif re.match(r"^[IVXLC]+\.", text):
            story.append(Paragraph(text, heading1))
        elif re.match(r"^\d+\.", text):
            story.append(Paragraph(text, heading2))
        elif re.match(r"^[A-Z]\.", text):
            story.append(Paragraph(text, heading3))
        elif text.startswith(("•", "-", "*")):
            story.append(Paragraph(text.lstrip("•-* ").strip(), bullet_style))
        else:
            story.append(Paragraph(text, normal_style))

        story.append(Spacer(1, 6))

    doc = SimpleDocTemplate(buffer, pagesize=A4)
    doc.build(story)

# ---------------- Views ----------------
@login_required
def generate_notes(request):
    if request.method == "POST":
        video_url = request.POST.get("query_text", "").strip()
        uploaded_file = request.FILES.get("query_file")

        transcript_text = None
        if video_url:
            transcript_text = get_transcript(video_url)
        elif uploaded_file:
            transcript_text = uploaded_file.read().decode("utf-8", errors="ignore")

        if not transcript_text:
            transcript_text = "Transcript not available, please provide valid input."

        # Gemini Prompt
        final_prompt = f"""
        You are an expert academic note generator.

        Task:
        - Read the following transcript carefully:
        {transcript_text[:12000]}   # keep shorter for speed
        - Create very detailed, exam-ready lecture notes.
        - Use clear hierarchy with "Lecture Title:", "Heading:", "Subheading:".
        - Use bullet points for lists.
        - Include definitions, formulas, step-by-step derivations, advantages/disadvantages, examples, and applications.
        - Ensure the notes are self-contained and exhaustive for exam prep.
        - Do NOT output markdown (** or ##). Just plain structured text.
        """

        notes_text = query_gemini(final_prompt)

        # Generate PDF
        buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        format_notes_to_pdf(notes_text, buffer)
        buffer.seek(0)

        return FileResponse(open(buffer.name, "rb"), as_attachment=True, filename="Lecture_Notes.pdf")

    return redirect("lecture_notes")


def lecture_notes(request):
    return render(request, "student/lecture_notes.html")



def student_list(request):
    students = StudentProfile.objects.filter(assigned_teacher__user=request.user)
    return render(request, 'teacher/student_list.html', {'students': students})

@login_required
def respond_queries(request):
    teacher_profile = TeacherProfile.objects.get(user=request.user)

    if request.method == 'POST':
        query_id = request.POST.get('query_id')
        response_text = request.POST.get('response')

        if query_id and response_text:
            query_obj = Query.objects.get(id=query_id)
            query_obj.response = response_text
            query_obj.responded_by = teacher_profile
            query_obj.save()
            return redirect('respond_queries')  # Refresh to remove from list

    # Only fetch unanswered queries
    queries = Query.objects.filter(response__isnull=True)

    query_data = []
    for query in queries:
        query_data.append({
            'id': query.id,
            'student_name': query.student_name.get_full_name(),
            'roll_number': query.student_roll.roll_number,
            'query_text': query.query_text,
            'query_image': query.query_image.url if query.query_image else None,
            'submitted_at': query.submitted_at,
        })

    return render(request, 'teacher/respond_query.html', {'queries': query_data})

@login_required
def view_responded_queries(request):
    student_profile = StudentProfile.objects.get(user=request.user)

    queries = Query.objects.filter(
        student=student_profile,
        response__isnull=False
    ).select_related('responded_by__user')

    query_data = []
    for query in queries:
        query_data.append({
            'id': query.id,
            'query_text': query.query_text,
            'query_image': query.query_image.url if query.query_image else None,
            'response': query.response,
            'teacher_name': query.responded_by.user.get_full_name() if query.responded_by else "N/A",
            'submitted_at': query.submitted_at,
        })

    return render(request, 'student/response_query.html', {'queries': query_data})


@login_required
def give_remarks(request):
    teacher_profile = TeacherProfile.objects.get(user=request.user)

    if request.method == 'POST':
        answer_id = request.POST.get('answer_id')
        remark_text = request.POST.get('remark_text')
        answer_type = request.POST.get('answer_type')  # <-- differentiate

        if answer_type == "student":
            answer = StudentAnswer.objects.get(id=answer_id)
        else:  # exam
            answer = ExamAnswer.objects.get(id=answer_id)

        answer.remarks = remark_text
        answer.save()

        return redirect('give_remarks')

    # Fetch unanswered Student Answers
    student_answers = StudentAnswer.objects.filter(
        question__teacher=teacher_profile,
        remarks__isnull=True
    ).select_related('question', 'student_name')

    student_list = []
    for ans in student_answers:
        desc = ans.question.description
        if "LaTeX Equation:" in desc:
            parts = desc.split("LaTeX Equation:")
            question_text = parts[0].strip()
            latex = parts[1].strip()
        else:
            question_text = desc.strip()
            latex = ""
        student_list.append({
            'id': ans.id,
            'answer_type': "student",
            'question_text': question_text,
            'latex': latex,
            'answer_text': ans.answer_text,
            'answer_file': ans.answer_file.url if ans.answer_file else None,  # ✅ FIX
            'remarks': ans.remarks,
            'student_name': ans.student_name.get_full_name(),
        })


    # Fetch unanswered Exam Answers
    exam_answers = ExamAnswer.objects.filter(
        exam__teacher=teacher_profile,
        remarks__isnull=True
    ).select_related('exam', 'question', 'student_name')

    exam_list = []
    for ans in exam_answers:
        exam_list.append({
            'id': ans.id,
            'answer_type': "exam",
            'exam_title': ans.exam.title,
            'question_text': ans.question.text,
            'latex': ans.question.latex,
            'answer_text': ans.answer_text,
            'answer_file': ans.answer_file.url if ans.answer_file else None,  # ✅ FIX
            'remarks': ans.remarks,
            'student_name': ans.student_name.get_full_name(),
        })


    context = {
        'student_answers': student_list,
        'exam_answers': exam_list,
    }

    return render(request, 'teacher/remarks.html', context)


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





# AI helpers + views (copy-paste into views.py)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import google.generativeai as genai
import re, os, mimetypes, logging
from django.db import models as djmodels
from .models import StudentAnswer, Query  # adjust import if your models located elsewhere

logger = logging.getLogger(__name__)

# (If you already configured genai earlier in file, this is harmless)
# genai.configure(api_key=GEMINI_API_KEY)

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

# -----------------------------
# Assign Question (teacher typed question)
# -----------------------------
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
        model = genai.GenerativeModel("gemini-1.5-flash")
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

# -----------------------------
# Respond Query (student asked, may have student-uploaded attachments stored server-side)
# -----------------------------
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
        model = genai.GenerativeModel("gemini-1.5-flash")
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

# -----------------------------
# Remarks (grading / AI-check) — returns {"feedback": "..."}
# -----------------------------
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
        model = genai.GenerativeModel("gemini-1.5-flash")
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

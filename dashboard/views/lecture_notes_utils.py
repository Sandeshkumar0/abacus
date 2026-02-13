

"""
Lecture notes generation utilities using AI.
Handles YouTube transcript extraction, Whisper transcription, and PDF generation.
Updated to use Groq (Llama 3) instead of OpenAI/Grok.
"""

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
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import yt_dlp
import whisper

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = None
if GROQ_API_KEY:
    client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
else:
    print("⚠️ GROQ_API_KEY not configured. AI features will not work.")


def clean_notes_text(text: str) -> str:
    """
    Remove markdown symbols (*, **) and extra formatting from output.
    """
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)  # remove **bold**
    text = re.sub(r"\*(.*?)\*", r"\1", text)      # remove *italic*
    text = text.replace("##", "").replace("#", "") # remove headings
    return text.strip()


def query_groq(prompt: str) -> str:
    """Query Groq with a prompt and return cleaned response."""
    if not client:
        return "⚠️ Groq API not configured."
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000
        )
        return clean_notes_text(response.choices[0].message.content)
    except Exception as e:
        print("Groq API error:", str(e))
        return f"⚠️ Error generating notes: {str(e)}"


def extract_youtube_id(url: str) -> str:
    """Extract YouTube video ID from URL."""
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


def format_notes_to_pdf(notes_text, buffer):
    """Format notes text into a well-structured PDF."""
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


@login_required
def generate_notes(request):
    """Generate lecture notes from YouTube video or uploaded transcript."""
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

        # Groq Prompt
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

        notes_text = query_groq(final_prompt)

        # Generate PDF
        buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        format_notes_to_pdf(notes_text, buffer)
        buffer.seek(0)

        return FileResponse(open(buffer.name, "rb"), as_attachment=True, filename="Lecture_Notes.pdf")

    return redirect("lecture_notes")

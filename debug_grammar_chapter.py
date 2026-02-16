import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from dashboard.models import Chapter, Question, ExamQuestion, StudentAnswer, ExamAnswer, StudentProfile

# Find the "Grammar and Composition" chapter
chapters = Chapter.objects.filter(name__icontains="Grammar")
print(f"Found {chapters.count()} chapters matching 'Grammar':")
for ch in chapters:
    print(f"  - ID {ch.id}: {ch.name} (Subject: {ch.subject.name if ch.subject else 'None'})")

if chapters.exists():
    grammar_chapter = chapters.first()
    print(f"\nAnalyzing Chapter: {grammar_chapter.name} (ID: {grammar_chapter.id})")
    
    # Check questions linked to this chapter
    questions = Question.objects.filter(chapter=grammar_chapter)
    print(f"  Assignment Questions linked: {questions.count()}")
    for q in questions[:5]:
        print(f"    - Q{q.id}: subtopic='{q.subtopic}', tags='{q.concept_tags}'")
    
    # Check exam questions
    from dashboard.models import Exam
    exams = Exam.objects.filter(chapter=grammar_chapter)
    print(f"  Exams linked: {exams.count()}")
    for ex in exams[:3]:
        exam_qs = ex.questions.all()
        print(f"    - Exam '{ex.title}': {exam_qs.count()} questions")
        for q in exam_qs[:3]:
            print(f"      - Q{q.id}: tags='{q.concept_tags}'")
    
    # Check student answers for this chapter
    student = StudentProfile.objects.first()
    if student:
        print(f"\nStudent Answers for {student.user.email}:")
        answers = StudentAnswer.objects.filter(
            student=student,
            question__chapter=grammar_chapter,
            marks_obtained__isnull=False
        )
        print(f"  Graded Assignment Answers: {answers.count()}")
        for ans in answers[:5]:
            print(f"    - Q{ans.question.id}: {ans.marks_obtained}/{ans.question.max_marks} | "
                  f"subtopic='{ans.question.subtopic}' | tags='{ans.question.concept_tags}'")

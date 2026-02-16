
import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from dashboard.models import StudentProfile, StudentAnswer, ExamAnswer, Chapter
from accounts.models import CustomUser

def verify_chapter_data():
    with open('debug_chapter_intelligence.txt', 'w') as f:
        f.write("--- Chapter Intelligence Data Verification ---\n\n")
        
        # Get all chapters
        chapters = Chapter.objects.all()
        f.write(f"Total Chapters: {chapters.count()}\n\n")
        
        for chapter in chapters[:5]:  # First 5 chapters
            f.write(f"\nChapter: {chapter.name} (ID: {chapter.id})\n")
            f.write(f"  Subject: {chapter.subject.name if chapter.subject else 'None'}\n")
            
            # Count assignment answers for this chapter
            assignment_count = StudentAnswer.objects.filter(
                question__chapter=chapter,
                marks_obtained__isnull=False
            ).count()
            
            # Count exam answers for this chapter
            exam_count = ExamAnswer.objects.filter(
                question__exam__chapter=chapter,
                marks_obtained__isnull=False
            ).count()
            
            f.write(f"  Graded Assignment Answers: {assignment_count}\n")
            f.write(f"  Graded Exam Answers: {exam_count}\n")
            f.write(f"  Total Graded Answers: {assignment_count + exam_count}\n")
            
            # Sample some answers
            if assignment_count > 0:
                sample = StudentAnswer.objects.filter(
                    question__chapter=chapter,
                    marks_obtained__isnull=False
                ).select_related('question', 'student__user')[:3]
                
                for ans in sample:
                    f.write(f"    Assignment: Student {ans.student.user.email} | Q{ans.question.id} | "
                           f"Marks: {ans.marks_obtained}/{ans.question.max_marks} | "
                           f"Subtopic: '{ans.question.subtopic}' | Tags: '{ans.question.concept_tags}'\n")
            
            if exam_count > 0:
                sample = ExamAnswer.objects.filter(
                    question__exam__chapter=chapter,
                    marks_obtained__isnull=False
                ).select_related('question', 'student__user')[:3]
                
                for ans in sample:
                    f.write(f"    Exam: Student {ans.student.user.email} | Q{ans.question.id} | "
                           f"Marks: {ans.marks_obtained}/{ans.question.marks} | "
                           f"Tags: '{ans.question.concept_tags}'\n")
    
    print("Debug output written to debug_chapter_intelligence.txt")

if __name__ == "__main__":
    verify_chapter_data()

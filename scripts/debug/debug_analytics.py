
import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from dashboard.models import StudentProfile, StudentAnswer, ExamAnswer, Question
from accounts.models import CustomUser
from django.db.models import Sum

def debug_student_data(student_email=None):
    with open('debug_output_analytics.txt', 'w') as f:
        f.write(f"\n--- Debugging Data for: {student_email or 'All Students'} ---\n")
        
        if student_email:
            students = StudentProfile.objects.filter(user__email=student_email)
        else:
            students = StudentProfile.objects.all()

        for student in students:
            f.write(f"\nStudent: {student.user.email} (ID: {student.user.id})\n")
            
            # 1. Check Assignments
            assignments = StudentAnswer.objects.filter(student=student)
            graded_assignments = assignments.filter(marks_obtained__isnull=False)
            f.write(f"  Total Assignments: {assignments.count()}\n")
            f.write(f"  Graded Assignments: {graded_assignments.count()}\n")
            
            for ans in graded_assignments[:5]:
                q = ans.question
                f.write(f"    - QID {q.id}: Marks {ans.marks_obtained}/{q.max_marks} | Tags: '{q.concept_tags}'\n")

            # 2. Check Exams
            exams = ExamAnswer.objects.filter(student=student)
            graded_exams = exams.filter(marks_obtained__isnull=False)
            f.write(f"  Total Exam Answers: {exams.count()}\n")
            f.write(f"  Graded Exam Answers: {graded_exams.count()}\n")

            for ans in graded_exams[:5]:
                q = ans.question
                f.write(f"    - QID {q.id}: Marks {ans.marks_obtained}/{q.marks} | Tags: '{q.concept_tags}'\n")

            # 3. Check Analytics Output directly
            from dashboard.analytics import calculate_student_metrics
            metrics = calculate_student_metrics(student.user.id)
            f.write(f"  Calculated Metrics: {metrics}\n")
            
    print("Debug output written to debug_output_analytics.txt")

if __name__ == "__main__":
    # Default to the student from previous logs if possible, or just run for all to find the active one
    # The user mentioned 'teststudent_auto' in previous context (ID 4)
    # Let's just run for all to be safe and see who has data.
    debug_student_data()

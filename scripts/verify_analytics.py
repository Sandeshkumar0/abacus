
import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "abacus_site.settings")
django.setup()

from dashboard.models import Question, StudentAnswer, StudentProfile
from accounts.models import CustomUser, TeacherProfile, StudentProfile as StudentProfileModel
from dashboard.analytics import calculate_student_metrics
from django.utils import timezone

def run_verification():
    print("--- Starting Analytics Machine Verification ---")
    
    # 1. Setup Test Data
    # Create Users
    try:
        teacher_user, _ = CustomUser.objects.get_or_create(email="test_teacher_ai@example.com", defaults={'full_name': 'AI Teacher', 'is_teacher': True})
        teacher_profile, _ = TeacherProfile.objects.get_or_create(user=teacher_user)
        
        student_user, _ = CustomUser.objects.get_or_create(email="test_student_ai@example.com", defaults={'full_name': 'AI Student', 'is_student': True})
        # Handle potential StudentProfile creation if not auto-created by signals
        student_profile, _ = StudentProfileModel.objects.get_or_create(
            user=student_user, 
            defaults={'roll_number': 'AI001', 'dob': '2010-01-01', 'phone': '1234567890', 'student_class': '10'}
        )
        print("✅ Users Created/Fetched")

        # Create Questions
        # Q1: Algebra, Easy, Correct
        q1, _ = Question.objects.get_or_create(
            description="Solve x + 5 = 10",
            teacher=teacher_profile,
            teacher_name=teacher_user,
            defaults={
                'max_marks': 10,
                'due_date': timezone.now(),
                'difficulty': 'Easy',
                'concept_tags': 'Algebra, Linear Equations'
            }
        )
        
        # Q2: Algebra, Medium, Wrong
        q2, _ = Question.objects.get_or_create(
            description="Solve 2x + 4 = 12",
            teacher=teacher_profile,
            teacher_name=teacher_user,
            defaults={
                'max_marks': 10,
                'due_date': timezone.now(),
                'difficulty': 'Medium',
                'concept_tags': 'Algebra'
            }
        )
        
        # Q3: Geometry, Hard, Correct
        q3, _ = Question.objects.get_or_create(
            description="Calculate area of circle with r=7",
            teacher=teacher_profile,
            teacher_name=teacher_user,
            defaults={
                'max_marks': 10,
                'due_date': timezone.now(),
                'difficulty': 'Hard',
                'concept_tags': 'Geometry'
            }
        )
        print("✅ Questions Created")

        # Create Answers
        StudentAnswer.objects.update_or_create(
            student=student_profile, question=q1,
            defaults={
                'student_name': student_user,
                'student_roll': student_profile,
                'marks_obtained': 10, # 100%
                'time_taken_seconds': 30
            }
        )
        
        StudentAnswer.objects.update_or_create(
            student=student_profile, question=q2,
            defaults={
                'student_name': student_user,
                'student_roll': student_profile,
                'marks_obtained': 2, # 20%
                'time_taken_seconds': 120
            }
        )
        
        StudentAnswer.objects.update_or_create(
            student=student_profile, question=q3,
            defaults={
                'student_name': student_user,
                'student_roll': student_profile,
                'marks_obtained': 9, # 90%
                'time_taken_seconds': 300
            }
        )
        print("✅ Answers Submitted")
        
    except Exception as e:
        print(f"❌ Setup Failed: {e}")
        return

    # 2. Run Analytics
    print("\n--- Running Calculate Student Metrics ---")
    metrics = calculate_student_metrics(student_user.id)
    
    if not metrics:
        print("❌ Analytics returned None")
        return

    # 3. Assertions
    print(f"Metrics Received: {metrics}")
    
    # Expected Accuracy: (10 + 2 + 9) / 30 = 21/30 = 70%
    # But logic separates Assign/Exam. Here all are Assignments.
    # Assignment Accuracy: 21/30 * 100 = 70.0%
    if metrics['assignment_accuracy'] == 70.0:
        print("✅ Assignment Accuracy Correct (70%)")
    else:
        print(f"❌ Assignment Accuracy Mismatch: Expected 70.0, got {metrics['assignment_accuracy']}")

    # Difficulty Analysis
    # Easy: 1/1 (100%), Medium: 0/1 (0%), Hard: 1/1 (100%)
    diff = metrics['difficulty_analysis']
    if diff['Easy'] == 100.0 and diff['Medium'] == 0.0 and diff['Hard'] == 100.0:
         print("✅ Difficulty Analysis Correct")
    else:
         print(f"❌ Difficulty Analysis Mismatch: {diff}")
         
    # Weak Areas
    # Algebra: (100% + 20%) / 2 = 60% -> Not Weak (<50)
    # Linear Equations: 100% -> Strong
    # Geometry: 90% -> Strong
    # Wait, q2 is 2/10 = 20%. q1 is 10/10 = 100%. Algebra avg = (10+2)/(10+10) = 12/20 = 60%.
    # Weak area threshold is < 50%. So Algebra is NOT weak.
    # Let's adjust q2 marks to be 0 to make Algebra weak? 
    # Current: 60%.
    
    strong = metrics['strong_areas']
    weak = metrics['weak_areas']
    
    if "Geometry (90%)" in strong:
        print("✅ Geometry identified as Strong Area")
    else:
        print(f"❌ Geometry missing from Strong Areas: {strong}")

    if not weak:
         print("✅ No weak areas correctly identified (lowest is 60%)")
         
    # 4. Improvement Trend
    print("\n--- Verifying Improvement Trend ---")
    from dashboard.analytics import get_student_improvement_trend
    trend = get_student_improvement_trend(student_user.id)
    print(f"Trend: {trend}")
    
    if len(trend) == 3:
        print("✅ Trend has 3 data points")
        accuracies = [t['accuracy'] for t in trend]
        if 100.0 in accuracies and 20.0 in accuracies and 90.0 in accuracies:
             print("✅ Trend accuracy values matches submissions")
    else:
        print(f"❌ Trend length mismatch: {len(trend)}")

    # 5. Group Intelligence
    print("\n--- Verifying Group Intelligence ---")
    from dashboard.analytics import calculate_group_metrics
    
    # Use class_name="10" which we assigned to our AI student
    group_metrics = calculate_group_metrics(class_name="10")
    
    if group_metrics:
        print(f"Group Metrics: {group_metrics}")
        
        # We only have 1 student in Class 10, so Group Avg should = Student Avg (approx)
        # Student Avg was (70+70)/2 = 70.0 (Wait, calculate_student_metrics does (Ass+Ex)/2)
        # But calculate_group_metrics averages the *overall_accuracy* of all students. 
        # So it should be 70.0.
        
        if group_metrics['avg_class_accuracy'] == 70.0:
            print("✅ Group Average Accuracy Correct (70.0%)")
        else:
             print(f"❌ Group Avg Mismatch: {group_metrics['avg_class_accuracy']}")
             
        # Check Top Performer / At Risk
        # 70% is > 40 and < 80. So neither Top nor At Risk.
        # Wait, <40 is At Risk. >80 is Top. 70 is middle.
        
        if not group_metrics['at_risk_students'] and not group_metrics['top_performers']:
             print("✅ Categorization Correct (Student is average)")
        
        # Check Weak/Strong Areas
        # Should be same as student: Geometry Strong.
        full_strong_str = str(group_metrics['group_strong_areas'])
        if "Geometry" in full_strong_str:
             print("✅ Group Strong Areas Correct")
    else:
        print("❌ Group Metrics returned None (No students found?)")

    print("\n--- Verification Complete ---")



if __name__ == "__main__":
    run_verification()

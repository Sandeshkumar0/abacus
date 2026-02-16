from django.db.models import Avg, Count, Sum, F, Q
from django.utils import timezone
import django.db.models
from .models import StudentAnswer, ExamAnswer, Question, ExamQuestion, StudentProfile


def calculate_student_metrics(student_id):
    """
    Calculate comprehensive academic metrics for a student.
    Returns a dictionary structured for the AI engine.
    """
    try:
        student = StudentProfile.objects.get(user__id=student_id)
    except StudentProfile.DoesNotExist:
        return None

    # --- 1. Accuracy Calculation ---
    
    # Assignment Accuracy
    assignments = StudentAnswer.objects.filter(student=student, marks_obtained__isnull=False).select_related('question')
    total_assignments = assignments.count()
    total_assignment_marks = assignments.aggregate(Sum('marks_obtained'))['marks_obtained__sum'] or 0
    total_possible_assignment_marks = assignments.aggregate(Sum('question__max_marks'))['question__max_marks__sum'] or 0
    
    assignment_accuracy = 0
    if total_possible_assignment_marks > 0:
        assignment_accuracy = (total_assignment_marks / total_possible_assignment_marks) * 100

    # Exam Accuracy
    exams = ExamAnswer.objects.filter(student=student, marks_obtained__isnull=False).select_related('question')
    total_exams = exams.count()
    total_exam_marks = exams.aggregate(Sum('marks_obtained'))['marks_obtained__sum'] or 0
    total_possible_exam_marks = exams.aggregate(Sum('question__marks'))['question__marks__sum'] or 0
    
    exam_accuracy = 0
    if total_possible_exam_marks > 0:
        exam_accuracy = (total_exam_marks / total_possible_exam_marks) * 100

    # Overall Accuracy
    overall_accuracy = 0
    if total_assignments + total_exams > 0:
        overall_accuracy = (assignment_accuracy + exam_accuracy) / 2  # Simple average for now

    # --- 2. Difficulty Analysis ---
    
    difficulty_stats = {'Easy': {'total': 0, 'correct': 0}, 'Medium': {'total': 0, 'correct': 0}, 'Hard': {'total': 0, 'correct': 0}}
    
    # Process Assignments
    for ans in assignments:
        diff = ans.question.difficulty
        if diff in difficulty_stats:
            difficulty_stats[diff]['total'] += 1
            # Assuming > 50% marks is "correct" for this granular stat, or proportional
            if ans.marks_obtained and ans.question.max_marks:
                if (ans.marks_obtained / ans.question.max_marks) >= 0.5:
                     difficulty_stats[diff]['correct'] += 1

    # Process Exams
    for ans in exams:
        diff = ans.question.difficulty
        if diff in difficulty_stats:
            difficulty_stats[diff]['total'] += 1
            if ans.marks_obtained and ans.question.marks:
                if (ans.marks_obtained / ans.question.marks) >= 0.5:
                     difficulty_stats[diff]['correct'] += 1
                     
    difficulty_metrics = {}
    for level, data in difficulty_stats.items():
        if data['total'] > 0:
            difficulty_metrics[level] = (data['correct'] / data['total']) * 100
        else:
            difficulty_metrics[level] = 0

    # --- 3. Concept / Weakness Analysis ---
    
    concept_performance = {} # { 'Algebra': {'total': 10, 'score': 8}, ... }
    
    def process_concepts(answer_obj, question_obj, marks_obtained, max_marks):
        if not question_obj.concept_tags:
            return
        tags = [t.strip() for t in question_obj.concept_tags.split(',')]
        for tag in tags:
            if tag not in concept_performance:
                concept_performance[tag] = {'total_questions': 0, 'total_score_pct': 0}
            
            concept_performance[tag]['total_questions'] += 1
            if max_marks > 0:
                pct = (marks_obtained / max_marks) * 100
                concept_performance[tag]['total_score_pct'] += pct

    for ans in assignments:
        process_concepts(ans, ans.question, ans.marks_obtained, ans.question.max_marks)
        
    for ans in exams:
         process_concepts(ans, ans.question, ans.marks_obtained, ans.question.marks)

    weak_areas = []
    strong_areas = []
    
    for tag, data in concept_performance.items():
        avg_score = data['total_score_pct'] / data['total_questions']
        if avg_score < 50:
            weak_areas.append(f"{tag} ({int(avg_score)}%)")
        elif avg_score > 80:
            strong_areas.append(f"{tag} ({int(avg_score)}%)")

    return {
        "student_name": student.user.get_full_name(),
        "overall_accuracy": round(overall_accuracy, 1),
        "assignment_accuracy": round(assignment_accuracy, 1),
        "exam_accuracy": round(exam_accuracy, 1),
        "difficulty_analysis": difficulty_metrics,
        "weak_areas": weak_areas,
        "strong_areas": strong_areas,
        "consistency_score": "High" if overall_accuracy > 70 else "Medium" if overall_accuracy > 40 else "Low" # Placeholder logic
    }

def get_student_behavioral_insights(student_id):
    """
    Analyze submission times and habits.
    """
    try:
        student = StudentProfile.objects.get(user__id=student_id)
    except StudentProfile.DoesNotExist:
        return {}
        
    submissions = StudentAnswer.objects.filter(student=student).values_list('submitted_at', flat=True)
    
    if not submissions:
        return {"insight": "No activity recorded yet."}
        
    morning_count = 0
    night_count = 0
    
    for sub_time in submissions:
        hour = sub_time.hour
        if 5 <= hour < 12:
            morning_count += 1
        elif 20 <= hour or hour < 4:
            night_count += 1
            
    total = len(submissions)
    
    insight = "Balanced study habits."
    if morning_count > (total * 0.6):
        insight = "Early bird: Most active in the morning."
    elif night_count > (total * 0.6):
        insight = "Night owl: Prefers studying late at night."
        
    return {
        "study_pattern": insight,
        "total_submissions": total
    }

def get_student_improvement_trend(student_id):
    """
    Calculate the accuracy trend over the last 10 assignments/exams.
    Returns a list of dicts: [{'date': '...', 'accuracy': 80}, ...]
    """
    try:
        student = StudentProfile.objects.get(user__id=student_id)
    except StudentProfile.DoesNotExist:
        return []

    # Combine Assignments and Exams, sort by date
    assignments = StudentAnswer.objects.filter(
        student=student, 
        marks_obtained__isnull=False
    ).select_related('question').annotate(
        date=F('submitted_at'),
        score=F('marks_obtained'),
        total=F('question__max_marks'),
        type=django.db.models.Value('Assignment', output_field=django.db.models.CharField())
    ).values('date', 'score', 'total', 'type')

    exams = ExamAnswer.objects.filter(
        student=student,
        marks_obtained__isnull=False
    ).select_related('question').annotate(
        date=F('submitted_at'),
        score=F('marks_obtained'),
        total=F('question__marks'),
        type=django.db.models.Value('Exam', output_field=django.db.models.CharField())
    ).values('date', 'score', 'total', 'type')
    
    # Merge and sort
    combined = sorted(list(assignments) + list(exams), key=lambda x: x['date'])
    
    trend = []
    for item in combined:
        if item['total'] > 0:
            accuracy = (item['score'] / item['total']) * 100
            trend.append({
                'date': item['date'].strftime("%Y-%m-%d"),
                'accuracy': round(accuracy, 1),
                'type': item['type']
            })
            
    return trend[-10:] # Return last 10 data points


def calculate_group_metrics(group_id=None, class_name=None):
    """
    Analyze performance for a StudentGroup or a Class.
    """
    students = StudentProfile.objects.none()
    
    if group_id:
        try:
            from .models import StudentGroup
            group = StudentGroup.objects.get(id=group_id)
            students = group.students.all()
        except Exception:
            pass
    elif class_name:
        students = StudentProfile.objects.filter(student_class=class_name)
        
    if not students.exists():
        return None

    # Aggregates
    total_students = students.count()
    at_risk_list = []
    top_performers_list = []
    student_accuracies = []

    # 1. Individual Performance stats
    for student in students:
        # Re-use student metrics (efficient enough for small classes)
        metrics = calculate_student_metrics(student.user.id)
        if not metrics:
            continue
            
        acc = metrics['overall_accuracy']
        student_accuracies.append(acc)
        
        # Categorize
        if acc < 40:
            at_risk_list.append({'name': metrics['student_name'], 'accuracy': acc})
        elif acc > 80:
            top_performers_list.append({'name': metrics['student_name'], 'accuracy': acc})

    # 2. Group Concept Analysis (Aggregating raw question data for the whole group)
    group_concept_performance = {} # {'Algebra': {'total_pct': 500, 'count': 10}, ...}

    # Helper to process answers
    def process_group_answers(answer_qs, is_exam=False):
        for ans in answer_qs:
            q = ans.question
            if not q.concept_tags:
                continue
            
            max_m = q.marks if is_exam else q.max_marks
            if max_m <= 0 or ans.marks_obtained is None: 
                continue
                
            pct = (ans.marks_obtained / max_m) * 100
            
            tags = [t.strip() for t in q.concept_tags.split(',')]
            for tag in tags:
                if tag not in group_concept_performance:
                    group_concept_performance[tag] = {'total_pct': 0, 'count': 0}
                group_concept_performance[tag]['total_pct'] += pct
                group_concept_performance[tag]['count'] += 1

    # Fetch all answers for these students
    assignments = StudentAnswer.objects.filter(student__in=students, marks_obtained__isnull=False).select_related('question')
    exams = ExamAnswer.objects.filter(student__in=students, marks_obtained__isnull=False).select_related('question')

    process_group_answers(assignments, is_exam=False)
    process_group_answers(exams, is_exam=True)
    
    group_weak_areas = []
    group_strong_areas = []
    
    for tag, data in group_concept_performance.items():
        if data['count'] > 0:
            avg = data['total_pct'] / data['count']
            if avg < 50:
                group_weak_areas.append(f"{tag} ({int(avg)}%)")
            elif avg > 75:
                group_strong_areas.append(f"{tag} ({int(avg)}%)")

    # Average Class Accuracy
    avg_class_acc = 0
    if student_accuracies:
        avg_class_acc = sum(student_accuracies) / len(student_accuracies)

    return {
        "total_students": total_students,
        "avg_class_accuracy": round(avg_class_acc, 1),
        "at_risk_students": at_risk_list,
        "top_performers": top_performers_list,
        "group_weak_areas": group_weak_areas,
        "group_strong_areas": group_strong_areas
    }



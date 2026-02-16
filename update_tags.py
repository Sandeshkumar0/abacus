
import os
import django
import sys
import random

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'abacus_site.settings')
django.setup()

from dashboard.models import Question, ExamQuestion

def update_question_tags():
    tags_pool = ["Algebra", "Geometry", "Calculus", "Trigonometry", "Number System", "Arithmetic"]

    print("--- Updating Assignment Questions ---")
    questions = Question.objects.all()
    count_q = 0
    for q in questions:
        if not q.concept_tags:
            text = q.description.lower() if q.description else ""
            tag = derive_tag(text, tags_pool)
            q.concept_tags = tag
            q.save()
            print(f"Updated Assignment QID {q.id}: Assigned tag '{tag}'")
            count_q += 1

    print("--- Updating Exam Questions ---")
    exam_questions = ExamQuestion.objects.all()
    count_e = 0
    for q in exam_questions:
        if not q.concept_tags:
            text = q.text.lower() if q.text else ""
            tag = derive_tag(text, tags_pool)
            q.concept_tags = tag
            q.save()
            print(f"Updated Exam QID {q.id}: Assigned tag '{tag}'")
            count_e += 1
            
    print(f"--- Updated {count_q} Assignment Questions and {count_e} Exam Questions ---")

def derive_tag(text, tags_pool):
    if "x" in text or "solve" in text or "equation" in text:
        return "Algebra"
    elif "triangle" in text or "circle" in text or "angle" in text or "area" in text:
        return "Geometry"
    elif "sin" in text or "cos" in text or "tan" in text:
        return "Trigonometry"
    elif "add" in text or "sum" in text or "calculate" in text:
        return "Arithmetic"
    else:
        return random.choice(tags_pool)

if __name__ == "__main__":
    update_question_tags()

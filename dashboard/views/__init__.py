"""
Dashboard views package.
This module imports all views from the organized submodules for backward compatibility.
"""

# Student views
from .student_views import (
    student_dashboard,
    submit_answer,
    download_answer_pdf,
    student_assign,
    student_profile,
    student_profile_edit,
    raise_query,
    view_remarks,
    get_exam_questions,
    attempt_exam,
    download_exam_answer_pdf,
    give_test,
    enroll_course,
    practice_questions_page,
    subject_list,
    chapter_list,
    chapter_detail,
    submit_practice_answer,
)

# Teacher views
from .teacher_views import (
    teacher_dashboard,
    teacher_profile,
    teacher_profile_edit,
    assign_questions,
    take_test,
    create_exam,
    student_list,
    add_student,
    view_student,
    edit_student,
    delete_student,
    export_students_csv,
    respond_queries,
    view_responded_queries,
    search_dashboard,
    add_course,
    manage_groups,
    create_group,
    give_remarks,
    lecture_notes,
    # Subject and Chapter Management
    manage_subjects,
    create_subject,
    edit_subject,
    delete_subject,
    create_chapter,
    edit_chapter,
    delete_chapter,
)

# AI utilities (exposed as views)
from .ai_utils import (
    generate_answer_assign,
    generate_answer_query,
    generate_remark_feedback,
    download_pdf,
    clean_ai_text,
    collect_attachments_from_instance,
    generate_practice_questions,
    generate_exam_questions,
    generate_student_report,
    suggest_syllabus,
    generate_weak_topic_practice,
    analyze_student_performance,
)

# Lecture notes utilities
from .lecture_notes_utils import (
    generate_notes,
    clean_notes_text,
    query_groq,
    extract_youtube_id,
    get_transcript_from_youtube,
    transcribe_with_whisper,
    get_transcript,
    format_notes_to_pdf,
)

__all__ = [
    # Student views
    'student_dashboard',
    'submit_answer',
    'download_answer_pdf',
    'student_assign',
    'student_profile',
    'student_profile_edit',
    'raise_query',
    'view_remarks',
    'get_exam_questions',
    'attempt_exam',
    'download_exam_answer_pdf',
    'give_test',
    'practice_questions_page',
    'subject_list',
    'chapter_list',
    'chapter_detail',
    'submit_practice_answer',
    
    # Teacher views
    'teacher_dashboard',
    'teacher_profile',
    'teacher_profile_edit',
    'assign_questions',
    'take_test',
    'create_exam',
    'student_list',
    'add_student',
    'view_student',
    'edit_student',
    'delete_student',
    'export_students_csv',
    'respond_queries',
    'view_responded_queries',
    'give_remarks',
    'lecture_notes',
    'manage_subjects',
    'create_subject',
    'edit_subject',
    'delete_subject',
    'create_chapter',
    'edit_chapter',
    'delete_chapter',
    
    # AI utilities
    'generate_answer_assign',
    'generate_answer_query',
    'generate_remark_feedback',
    'download_pdf',
    'clean_ai_text',
    'collect_attachments_from_instance',
    'generate_practice_questions',
    'generate_exam_questions',
    'generate_student_report',
    'suggest_syllabus',
    'generate_weak_topic_practice',
    'analyze_student_performance',
    
    # Lecture notes utilities
    'generate_notes',
    'clean_notes_text',
    'query_groq',
    'extract_youtube_id',
    'get_transcript_from_youtube',
    'transcribe_with_whisper',
    'get_transcript',
    'format_notes_to_pdf',
]

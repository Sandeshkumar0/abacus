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
    give_remarks,
    lecture_notes,
)

# AI utilities (exposed as views)
from .ai_utils import (
    generate_answer_assign,
    generate_answer_query,
    generate_remark_feedback,
    download_pdf,
    extract_text_from_response,
    clean_ai_text,
    collect_attachments_from_instance,
    build_gemini_parts,
)

# Lecture notes utilities
from .lecture_notes_utils import (
    generate_notes,
    clean_notes_text,
    query_gemini,
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
    
    # AI utilities
    'generate_answer_assign',
    'generate_answer_query',
    'generate_remark_feedback',
    'download_pdf',
    'extract_text_from_response',
    'clean_ai_text',
    'collect_attachments_from_instance',
    'build_gemini_parts',
    
    # Lecture notes utilities
    'generate_notes',
    'clean_notes_text',
    'query_gemini',
    'extract_youtube_id',
    'get_transcript_from_youtube',
    'transcribe_with_whisper',
    'get_transcript',
    'format_notes_to_pdf',
]

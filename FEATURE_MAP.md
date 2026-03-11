# Abacus Feature-to-Code Map

This file is a quick index to find where each feature is implemented.
Use this as a direct jump guide when debugging or changing behavior.

## 1) Project Entry, Routing, Settings

- Main URL router: `abacus_site/urls.py`
- Django settings (apps, i18n, middleware, auth model): `abacus_site/settings.py`
- App-level routes:
  - Public site: `core/urls.py`
  - Auth + section management: `accounts/urls.py`
  - Dashboard (student/teacher/parent + APIs): `dashboard/urls.py`

## 2) Authentication and Role System

- Custom user + roles + manager: `accounts/models.py` (`CustomUser`, `CustomUserManager`)
- Email login backend: `accounts/backends.py`
- Login/Signup/Logout:
  - `accounts/views.py`
  - `student_login`, `student_signup`
  - `teacher_login`, `teacher_signup_view`
  - `parent_login`, `parent_signup`
  - `student_logout_view`, `teacher_logout_view`, `parent_logout_view`

## 3) Section and Teacher Assignment Management

- Models:
  - Section: `accounts/models.py` (`Section`)
  - Teacher-section link: `accounts/models.py` (`TeacherSectionAssignment`)
- Admin configuration:
  - `accounts/admin.py`
  - `SectionAdminForm`, `SectionAdmin` (bulk section create)
  - `TeacherSectionAssignmentAdminForm`, `TeacherSectionAssignmentAdmin` (multi-section + subject assignment)
- Dashboard page (non-Django-admin):
  - Route: `accounts/urls.py` -> `sections/manage/`
  - View: `accounts/views.py` -> `section_management`
  - Template: `accounts/templates/admin/section_management.html`

## 4) Access Control (Who Can See What)

- Central logic: `dashboard/access_control.py`
  - `get_accessible_sections`
  - `get_accessible_students`
  - `get_accessible_subjects`
  - `can_access_student`
  - `can_access_subject`
- Role decorators:
  - `dashboard/decorators.py`
  - `role_required`, `teacher_required_json`, `student_required_json`, `student_access_required_json`

## 5) Subject and Chapter Management

- Models:
  - Subject: `dashboard/models.py` (`Subject`)
  - Subject-teacher-section mapping: `dashboard/models.py` (`SubjectTeacherAssignment`)
  - Chapter: `dashboard/models.py` (`Chapter`)
  - Subject resources: `dashboard/models.py` (`SubjectResource`)
- Important validation:
  - Class/section compatibility: `dashboard/models.py` (`SubjectTeacherAssignment.clean`)
- Teacher views:
  - `dashboard/views/teacher_views.py`
  - `manage_subjects`
  - `create_subject`
  - `edit_subject`
  - `delete_subject`
  - `create_chapter`
  - `edit_chapter`
  - `delete_chapter`
  - `teacher_subject_resources`
- Student consumption:
  - `dashboard/views/student_views.py`
  - `subject_list`
  - `chapter_list`
  - `chapter_detail`
- Templates:
  - Teacher: `core/templates/teacher/manage_subjects.html`, `create_subject.html`, `subject_resources.html`
  - Student: `core/templates/student/subject_list.html`, `chapter_list.html`, `chapter_detail.html`

## 6) Teacher Dashboard Features

- Main dashboard + profile:
  - `dashboard/views/teacher_views.py`
  - `teacher_dashboard`, `teacher_profile`, `teacher_profile_edit`
- Student management by teacher:
  - `student_list`, `add_student`, `view_student`, `edit_student`, `delete_student`, `export_students_csv`
  - Templates in `core/templates/teacher/` (`student_list.html`, `view_student.html`, etc.)
- Question/exam flow:
  - `assign_questions`, `take_test`, `create_exam`
  - `respond_queries`, `give_remarks`
- Groups and competition:
  - `manage_groups`, `create_group`, `group_competition`
- Notes/messages/attendance/holidays:
  - `upload_notes`, `post_class_message`, `attendance_marking`, `manage_holidays`, `teacher_assigned_sections`

## 7) Student Dashboard Features

- Main dashboard: `dashboard/views/student_views.py` -> `student_dashboard`
- Assignments and submissions:
  - `student_assign`, `submit_answer`, `download_answer_pdf`
- Exams:
  - `give_test`, `get_exam_questions`, `attempt_exam`, `download_exam_answer_pdf`
- Queries and remarks:
  - `raise_query`, `view_remarks`, `view_responded_queries`
- Lecture notes and virtual abacus:
  - `lecture_notes`, `virtual_abacus`, `virtual_abacus_ai_tutor`, `generate_notes`
- Practice and analytics:
  - `practice_questions_page`, `submit_practice_answer`
  - `analyze_student_performance`, `generate_weak_topic_practice`, `topic_learning_content`
- Attendance and holidays:
  - `student_attendance`, `holiday_calendar`

## 8) Parent Dashboard Features

- Parent guard + child linking helpers:
  - `dashboard/views/parent_views.py`
  - `_parent_guard`, `_linked_children`, `_select_child`
- Main pages:
  - `parent_dashboard`
  - `parent_children`
  - `parent_assignments`
  - `parent_notes`
  - `parent_messages`
  - `parent_holidays`
  - `parent_performance`
  - `parent_exam_portion`
- Parent AI utilities:
  - `parent_assignment_explain`
  - `parent_assignment_simplify_remark`

## 9) Holiday and Announcement System

- Models:
  - `dashboard/models.py` -> `Holiday`, `Announcement`, `AnnouncementRead`
- Admin behaviors:
  - `dashboard/admin.py`
  - `AnnouncementAdmin.save_model` (creates notifications)
  - `HolidayAdmin.save_model` (creates notifications)
- Teacher portal holiday creation:
  - `dashboard/views/teacher_views.py` -> `manage_holidays`
- Student/parent holiday screens:
  - `dashboard/views/student_views.py` -> `holiday_calendar`
  - `dashboard/views/parent_views.py` -> `parent_holidays`

## 10) Notifications and Signals

- Notification model: `dashboard/models.py` (`Notification`)
- Auto events: `dashboard/signals.py`
  - New question assigned
  - New exam assigned
  - Answer graded/submitted
  - Query events
  - Group competition events
- Signal registration hook: `dashboard/apps.py` (`ready`)
- Realtime consumer: `dashboard/consumers.py`
- Notification UI partial: `core/templates/includes/notification_widget.html`

## 11) Dashboard API and Metrics

- API views:
  - `dashboard/views/dashboard_api.py`
  - `student_dashboard_snapshot`
  - `teacher_dashboard_snapshot`
  - `teacher_at_risk_students`
- Service layer:
  - `dashboard/services/dashboard_metrics.py`
- Analytics helpers:
  - `dashboard/analytics.py`

## 12) AI / LLM Utility Layer

- Main AI utils: `dashboard/views/ai_utils.py`
  - Exam/question generation
  - Feedback/remark helpers
  - Formatting cleanup utilities (markdown stripping, sanitization)
- Lecture-note specific utilities: `dashboard/views/lecture_notes_utils.py`

## 13) Django Admin Registrations (Quick List)

- Accounts admin: `accounts/admin.py`
  - `CustomUserAdmin`, `TeacherProfileAdmin`, `StudentProfileAdmin`
  - `SectionAdmin`, `TeacherSectionAssignmentAdmin`
  - `ParentProfileAdmin`, `ParentStudentRelationAdmin`
- Dashboard admin: `dashboard/admin.py`
  - `SubjectAdmin`, `SubjectTeacherAssignmentAdmin`, `ChapterAdmin`, `SubjectResourceAdmin`
  - `AnnouncementAdmin`, `HolidayAdmin`
  - Plus course/exam/query/notification and other models
- Core admin: `core/admin.py`
  - `BlogCategoryAdmin`, `BlogPostAdmin`, `ContactSubmissionAdmin`

## 14) Public Website (Core App)

- Routes: `core/urls.py`
- Views: `core/views.py`
  - `home`, `about`, `courses`, `franchise`
  - `blog_list`, `blog_detail`, `subscribe_newsletter`
  - `contact`, `privacy`, `terms`, `refund`
  - `virtual_abacus`

## 15) Templates by Area

- Public site: `core/templates/*.html`
- Student: `core/templates/student/*.html`
- Teacher: `core/templates/teacher/*.html`
- Parent: `core/templates/parent/*.html`
- Auth/reset: `core/templates/registration/*.html`

## 16) Data Model Center

- Domain models (main): `dashboard/models.py`
- User and profile models: `accounts/models.py`
- CMS-like models (blog/contact): `core/models.py`

## 17) Background / Command Utilities

- Management command: `dashboard/management/commands/cleanup_expired_announcements.py`

---

If you want, next step I can generate `FEATURE_MAP_DETAILED.md` with:
- exact URL -> view -> template mapping line-by-line,
- and a "change checklist" (which files to edit for each feature).

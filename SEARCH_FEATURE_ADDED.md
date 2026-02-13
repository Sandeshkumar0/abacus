# 🔍 Universal Search Feature Added

## Overview
I have implemented a **Universal Search** feature for the Teacher Dashboard and fixed the "Search" button in the sidebar.

## ✨ Features
Searching now allows you to find everything in one place:
1.  **🎓 Students**: Search by Name, Email, or Roll Number.
2.  **📝 Assignments**: Search by Description.
3.  **📚 Exams**: Search by Title.
4.  **❓ Queries**: Search by Student Name or Query Text.

## 🛠️ Changes Made
1.  **New View**: Added `search_dashboard` in `teacher_views.py`.
2.  **New Template**: Created `teacher/search_results.html` to display categorized results.
3.  **Sidebar Update**: Linked the "Search" button in the sidebar to the new search page.
4.  **Code Cleanup**: Refactored `teacher_views.py` to remove duplicate code.

## 🚀 How to Use
1.  Click the **Search** button in the sidebar.
2.  Type any keyword (e.g., "John", "Math", "Exam").
3.  See instant results across all categories.

"""
Django signals for creating and sending real-time notifications
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Question, Exam, Notification, StudentAnswer, ExamAnswer, Query
from accounts.models import StudentProfile, CustomUser


@receiver(post_save, sender=Question, dispatch_uid="notify_students_new_test_unique")
def notify_students_new_test(sender, instance, created, **kwargs):
    """Send notification to all students when a new test/question is assigned"""
    if created:  # Only for newly created questions
        # Get all students
        students = CustomUser.objects.filter(is_student=True)
        
        channel_layer = get_channel_layer()
        
        for student in students:
            # Create notification in database
            notification = Notification.objects.create(
                recipient=student,
                notification_type='test_assigned',
                title=f'New Test Assigned',
                message=f'Teacher {instance.teacher_name.get_full_name()} has assigned a new test. Due: {instance.due_date.strftime("%b %d, %Y %I:%M %p")}',
                link='/portal/dashboard/student/view-assign/',  # Link to view assigned questions
                question=instance
            )
            
            # Send real-time notification via WebSocket
            notification_data = {
                'id': notification.id,
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'link': notification.link,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat()
            }
            
            # Send to user's WebSocket group
            group_name = f"notifications_{student.id}"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification_message',
                    'notification': notification_data
                }
            )


@receiver(post_save, sender=Exam, dispatch_uid="notify_students_new_exam_unique")
def notify_students_new_exam(sender, instance, created, **kwargs):
    """Send notification to all students when a new exam is assigned"""
    if created:  # Only for newly created exams
        # Get all students
        students = CustomUser.objects.filter(is_student=True)
        
        channel_layer = get_channel_layer()
        
        for student in students:
            # Create notification in database
            notification = Notification.objects.create(
                recipient=student,
                notification_type='exam_assigned',
                title=f'New Exam: {instance.title}',
                message=f'Teacher {instance.teacher_name.get_full_name()} has assigned a new exam. Total Marks: {instance.total_marks}. Due: {instance.due_date.strftime("%b %d, %Y %I:%M %p")}',
                link='/portal/dashboard/student/give-test/',  # Link to give test/exam
                exam=instance
            )
            
            # Send real-time notification via WebSocket
            notification_data = {
                'id': notification.id,
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'link': notification.link,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat()
            }
            
            # Send to user's WebSocket group
            group_name = f"notifications_{student.id}"
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification_message',
                    'notification': notification_data
                }
            )


@receiver(post_save, sender=StudentAnswer, dispatch_uid="notify_answer_events_unique")
def notify_answer_events(sender, instance, created, **kwargs):
    """Handle notifications for student answer events"""
    channel_layer = get_channel_layer()
    
    # Notify student when answer is graded
    if not created and instance.remarks:
        student_user = instance.student_name
        marks_info = f" Max Marks: {instance.question.max_marks}" if instance.question and instance.question.max_marks else ""
        
        notification = Notification.objects.create(
            recipient=student_user,
            notification_type='answer_graded',
            title='✅ Answer Graded',
            message=f'Your answer has been graded.{marks_info} Check your feedback!',
            link='/portal/dashboard/student/view-remarks/',
            question=instance.question
        )
        
        notification_data = {
            'id': notification.id,
            'type': notification.notification_type,
            'title': notification.title,
            'message': notification.message,
            'link': notification.link,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat()
        }
        
        group_name = f"notifications_{student_user.id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': notification_data
            }
        )
    
    # Notify teacher when student submits answer
    if created:
        teacher_user = instance.question.teacher_name
        student_name = instance.student_name.get_full_name()
        
        notification = Notification.objects.create(
            recipient=teacher_user,
            notification_type='general',
            title='📝 New Answer Submitted',
            message=f'{student_name} has submitted an answer. Question #{instance.question.id}',
            link='/portal/dashboard/teacher/give-remarks/',
            question=instance.question
        )
        
        notification_data = {
            'id': notification.id,
            'type': notification.notification_type,
            'title': notification.title,
            'message': notification.message,
            'link': notification.link,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat()
        }
        
        group_name = f"notifications_{teacher_user.id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': notification_data
            }
        )


@receiver(post_save, sender=Query, dispatch_uid="notify_query_events_unique")
def notify_query_events(sender, instance, created, **kwargs):
    """Handle notifications for query events"""
    channel_layer = get_channel_layer()
    
    # Notify student when query is answered
    if not created and instance.response:
        student_user = instance.student_name
        
        notification = Notification.objects.create(
            recipient=student_user,
            notification_type='query_responded',
            title='💬 Your Query Has Been Answered',
            message=f'Teacher has responded to your query. Check it out!',
            link='/portal/dashboard/student/view-responded-queries/',
        )
        
        notification_data = {
            'id': notification.id,
            'type': notification.notification_type,
            'title': notification.title,
            'message': notification.message,
            'link': notification.link,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat()
        }
        
        group_name = f"notifications_{student_user.id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': notification_data
            }
        )
    
    # Notify teacher when student raises query
    if created:
        try:
            student_profile = StudentProfile.objects.get(user=instance.student_name)
            if student_profile.assigned_teacher:
                teacher_user = student_profile.assigned_teacher.user
                student_name = instance.student_name.get_full_name()
                query_preview = instance.query_text[:50] + "..." if len(instance.query_text) > 50 else instance.query_text
                
                notification = Notification.objects.create(
                    recipient=teacher_user,
                    notification_type='general',
                    title='❓ New Query Received',
                    message=f'{student_name} has raised a query: "{query_preview}"',
                    link='/portal/dashboard/teacher/queries/',
                )
                
                notification_data = {
                    'id': notification.id,
                    'type': notification.notification_type,
                    'title': notification.title,
                    'message': notification.message,
                    'link': notification.link,
                    'is_read': notification.is_read,
                    'created_at': notification.created_at.isoformat()
                }
                
                group_name = f"notifications_{teacher_user.id}"
                async_to_sync(channel_layer.group_send)(
                    group_name,
                    {
                        'type': 'notification_message',
                        'notification': notification_data
                    }
                )
        except StudentProfile.DoesNotExist:
            pass


@receiver(post_save, sender=ExamAnswer, dispatch_uid="notify_teacher_exam_submitted_unique")
def notify_teacher_exam_submitted(sender, instance, created, **kwargs):
    """Notify teacher when student submits exam answer"""
    if created:
        teacher_user = instance.exam.teacher_name
        student_name = instance.student_name.get_full_name()
        
        notification = Notification.objects.create(
            recipient=teacher_user,
            notification_type='general',
            title='📋 Exam Answer Submitted',
            message=f'{student_name} has submitted an answer for exam: {instance.exam.title}',
            link='/portal/dashboard/teacher/give-remarks/',
            exam=instance.exam
        )
        
        channel_layer = get_channel_layer()
        notification_data = {
            'id': notification.id,
            'type': notification.notification_type,
            'title': notification.title,
            'message': notification.message,
            'link': notification.link,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat()
        }
        
        group_name = f"notifications_{teacher_user.id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': notification_data
            }
        )

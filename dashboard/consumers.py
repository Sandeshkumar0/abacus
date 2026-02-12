"""
WebSocket consumers for real-time notifications
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling real-time notifications
    Each user connects to their own notification channel
    """
    
    async def connect(self):
        """Called when WebSocket connection is established"""
        self.user = self.scope["user"]
        
        # Only allow authenticated users
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Create a unique group name for this user
        self.group_name = f"notifications_{self.user.id}"
        
        # Join the user's notification group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept the WebSocket connection
        await self.accept()
        
        # Send initial unread count
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to notification system',
            'unread_count': unread_count
        }))
    
    async def disconnect(self, close_code):
        """Called when WebSocket connection is closed"""
        if hasattr(self, 'group_name'):
            # Leave the notification group
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """
        Called when we receive a message from WebSocket
        Handles mark as read, fetch notifications, etc.
        """
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'mark_read':
                notification_id = data.get('notification_id')
                await self.mark_notification_read(notification_id)
                
            elif action == 'mark_all_read':
                await self.mark_all_notifications_read()
                
            elif action == 'fetch_notifications':
                notifications = await self.get_recent_notifications()
                await self.send(text_data=json.dumps({
                    'type': 'notifications_list',
                    'notifications': notifications
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
    
    async def notification_message(self, event):
        """
        Called when a notification is sent to this user's group
        Forwards the notification to the WebSocket
        """
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification']
        }))
    
    @database_sync_to_async
    def get_unread_count(self):
        """Get count of unread notifications for current user"""
        from dashboard.models import Notification
        return Notification.objects.filter(
            recipient=self.user,
            is_read=False
        ).count()
    
    @database_sync_to_async
    def get_recent_notifications(self):
        """Get recent notifications for current user"""
        from dashboard.models import Notification
        notifications = Notification.objects.filter(
            recipient=self.user
        )[:20]  # Last 20 notifications
        
        return [{
            'id': n.id,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'link': n.link,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat()
        } for n in notifications]
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark a specific notification as read"""
        from dashboard.models import Notification
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=self.user
            )
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False
    
    @database_sync_to_async
    def mark_all_notifications_read(self):
        """Mark all notifications as read for current user"""
        from dashboard.models import Notification
        Notification.objects.filter(
            recipient=self.user,
            is_read=False
        ).update(is_read=True)
        return True

/**
 * Real-time Notification System using WebSockets
 */

class NotificationManager {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this.init();
    }

    init() {
        this.connect();
        this.setupEventListeners();
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/notifications/`;

        try {
            this.socket = new WebSocket(wsUrl);

            this.socket.onopen = () => {
                console.log('✅ WebSocket connected');
                this.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
            };

            this.socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };

            this.socket.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
            };

            this.socket.onclose = () => {
                console.log('🔌 WebSocket disconnected');
                this.updateConnectionStatus(false);
                this.attemptReconnect();
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
        }
    }

    handleMessage(data) {
        switch (data.type) {
            case 'connection_established':
                this.updateUnreadCount(data.unread_count);
                break;
            case 'new_notification':
                this.showNotification(data.notification);
                this.playNotificationSound();
                break;
            case 'notifications_list':
                this.displayNotificationsList(data.notifications);
                break;
        }
    }

    showNotification(notification) {
        // Update unread count
        const badge = document.getElementById('notification-badge');
        if (badge) {
            const current = parseInt(badge.textContent) || 0;
            badge.textContent = current + 1;
            badge.style.display = 'inline-block';
        }

        // Show toast notification
        this.showToast(notification);

        // Add to notification list if visible
        this.prependToNotificationList(notification);
    }

    showToast(notification) {
        const toast = document.createElement('div');
        toast.className = 'notification-toast';
        toast.innerHTML = `
            <div class="toast-header">
                <strong>${notification.title}</strong>
                <button class="toast-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div class="toast-body">${notification.message}</div>
        `;

        document.body.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    playNotificationSound() {
        // Optional: Play notification sound
        const audio = new Audio('/static/sounds/notification.mp3');
        audio.volume = 0.3;
        audio.play().catch(() => { }); // Ignore if sound file doesn't exist
    }

    updateUnreadCount(count) {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            badge.textContent = count;
            badge.style.display = count > 0 ? 'inline-block' : 'none';
        }

        // Update the status dot color
        const indicator = document.getElementById('connection-status');
        if (indicator) {
            if (count > 0) {
                indicator.className = 'unread'; // Green
                indicator.title = `${count} unread notifications`;
            } else {
                indicator.className = 'read'; // Red
                indicator.title = 'No new notifications';
            }
        }
    }

    markAsRead(notificationId) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                action: 'mark_read',
                notification_id: notificationId
            }));
        }
    }

    markAllAsRead() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                action: 'mark_all_read'
            }));
            this.updateUnreadCount(0);
        }
    }

    fetchNotifications() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({
                action: 'fetch_notifications'
            }));
        }
    }

    prependToNotificationList(notification) {
        const list = document.getElementById('notifications-list');
        if (!list) return;

        const item = this.createNotificationElement(notification);
        list.insertBefore(item, list.firstChild);
    }

    createNotificationElement(notification) {
        const div = document.createElement('div');
        div.className = `notification-item ${notification.is_read ? 'read' : 'unread'}`;
        div.dataset.notificationId = notification.id;
        div.innerHTML = `
            <div class="notification-content">
                <strong>${notification.title}</strong>
                <p>${notification.message}</p>
                <small>${new Date(notification.created_at).toLocaleString()}</small>
            </div>
            ${notification.link ? `<a href="${notification.link}" class="notification-link">View</a>` : ''}
        `;

        // Mark as read when clicked
        div.addEventListener('click', (e) => {
            if (!notification.is_read) {
                this.markAsRead(notification.id);
                div.classList.remove('unread');
                div.classList.add('read');

                // Update unread count
                const badge = document.getElementById('notification-badge');
                if (badge) {
                    const current = parseInt(badge.textContent) || 0;
                    const newCount = Math.max(0, current - 1);
                    this.updateUnreadCount(newCount);
                }
            }
        });

        return div;
    }

    displayNotificationsList(notifications) {
        const list = document.getElementById('notifications-list');
        if (!list) return;

        list.innerHTML = notifications.length > 0
            ? notifications.map(n => this.createNotificationElement(n).outerHTML).join('')
            : '<p class="no-notifications">No notifications yet</p>';
    }

    updateConnectionStatus(connected) {
        // We are now using this dot for unread status, but we can log connection status
        console.log(`WebSocket ${connected ? 'Connected' : 'Disconnected'}`);
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            setTimeout(() => this.connect(), this.reconnectDelay);
        }
    }

    setupEventListeners() {
        // Fetch notifications when bell icon is clicked
        document.addEventListener('click', (e) => {
            if (e.target.closest('#notification-bell')) {
                this.fetchNotifications();
            }
        });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.notificationManager = new NotificationManager();
});

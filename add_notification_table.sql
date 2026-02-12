-- SQL to add Notification table to existing database
-- Run this if migrations are not working

CREATE TABLE IF NOT EXISTS dashboard_notification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL,
    notification_type VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    link VARCHAR(500),
    is_read BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL,
    question_id INTEGER,
    exam_id INTEGER,
    FOREIGN KEY (recipient_id) REFERENCES accounts_customuser(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES dashboard_question(id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id) REFERENCES dashboard_exam(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notification_recipient ON dashboard_notification(recipient_id);
CREATE INDEX IF NOT EXISTS idx_notification_created ON dashboard_notification(created_at);
CREATE INDEX IF NOT EXISTS idx_notification_is_read ON dashboard_notification(is_read);

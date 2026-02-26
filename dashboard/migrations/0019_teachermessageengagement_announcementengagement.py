from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0018_exam_duration_minutes_exam_timer_enabled"),
        ("accounts", "0003_customuser_role_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeacherMessageEngagement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_liked", models.BooleanField(default=False)),
                ("comment_text", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="engagements", to="dashboard.teacherclassmessage")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_message_engagements", to="accounts.studentprofile")),
            ],
            options={
                "ordering": ["-updated_at"],
                "unique_together": {("message", "student")},
            },
        ),
        migrations.CreateModel(
            name="AnnouncementEngagement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_liked", models.BooleanField(default=False)),
                ("comment_text", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("announcement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="engagements", to="dashboard.announcement")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="announcement_engagements", to="accounts.studentprofile")),
            ],
            options={
                "ordering": ["-updated_at"],
                "unique_together": {("announcement", "student")},
            },
        ),
    ]

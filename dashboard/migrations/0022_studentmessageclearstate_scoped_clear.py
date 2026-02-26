from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0021_question_exam_section"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentmessageclearstate",
            name="announcements_cleared_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="studentmessageclearstate",
            name="teacher_messages_cleared_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

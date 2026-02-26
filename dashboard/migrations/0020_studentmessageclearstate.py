from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_customuser_role_and_more"),
        ("dashboard", "0019_teachermessageengagement_announcementengagement"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentMessageClearState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cleared_at", models.DateTimeField()),
                ("student", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="message_clear_state", to="accounts.studentprofile")),
            ],
        ),
    ]

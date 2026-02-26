from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_customuser_role_and_more"),
        ("dashboard", "0020_studentmessageclearstate"),
    ]

    operations = [
        migrations.AddField(
            model_name="exam",
            name="section",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="exams",
                to="accounts.section",
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="section",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="questions",
                to="accounts.section",
            ),
        ),
    ]


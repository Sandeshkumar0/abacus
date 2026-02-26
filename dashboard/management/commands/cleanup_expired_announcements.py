from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import Announcement


class Command(BaseCommand):
    help = "Delete expired announcements based on expires_at or auto_delete_after_days."

    def handle(self, *args, **options):
        now = timezone.now()

        expired_by_datetime_qs = Announcement.objects.filter(expires_at__isnull=False, expires_at__lte=now)
        expired_by_datetime_count = expired_by_datetime_qs.count()
        expired_by_datetime_qs.delete()

        expired_by_retention_count = 0
        retention_candidates = Announcement.objects.filter(expires_at__isnull=True).only(
            "id",
            "created_at",
            "auto_delete_after_days",
        )
        retention_delete_ids = []
        for announcement in retention_candidates:
            max_age_days = announcement.auto_delete_after_days or 30
            if (now - announcement.created_at).days >= max_age_days:
                retention_delete_ids.append(announcement.id)
        if retention_delete_ids:
            expired_by_retention_count = len(retention_delete_ids)
            Announcement.objects.filter(id__in=retention_delete_ids).delete()

        total = expired_by_datetime_count + expired_by_retention_count
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {total} expired announcements "
                f"({expired_by_datetime_count} by expires_at, {expired_by_retention_count} by retention)."
            )
        )

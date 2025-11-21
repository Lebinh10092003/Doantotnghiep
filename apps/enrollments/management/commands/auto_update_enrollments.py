from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.enrollments.services import auto_update_status


class Command(BaseCommand):
    help = "Auto-update enrollment status based on remaining sessions and end_date."

    def handle(self, *args, **options):
        today = timezone.now().date()
        qs = Enrollment.objects.filter(status__in=[EnrollmentStatus.NEW, EnrollmentStatus.ACTIVE, EnrollmentStatus.PAUSED])
        updated = 0
        for enrollment in qs.iterator():
            if auto_update_status(enrollment, today=today):
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Processed {qs.count()} enrollments, updated {updated}."))

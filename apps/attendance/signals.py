from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.attendance.models import Attendance
from apps.billing.models import BillingEntry
from apps.enrollments.models import Enrollment
from apps.enrollments.services import (
    ATTENDED_STATUSES,
    auto_update_status,
    recalc_sessions_consumed,
)


@receiver(pre_save, sender=Attendance)
def _store_old_status(sender, instance: Attendance, **kwargs):
    if instance.pk:
        try:
            instance._old_status = Attendance.objects.get(pk=instance.pk).status
        except Attendance.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Attendance)
def _sync_enrollment_after_attendance(sender, instance: Attendance, **kwargs):
    new_status = instance.status
    old_status = getattr(instance, "_old_status", None)
    status_changed = old_status != new_status

    if not status_changed and instance.pk:
        # No status change -> nothing to update
        return

    try:
        enrollment = (
            Enrollment.objects.filter(
                student=instance.student,
                klass=instance.session.klass,
            )
            .order_by("-id")
            .first()
        )
    except Enrollment.DoesNotExist:
        enrollment = None

    if not enrollment:
        return

    # If status change from consuming to non-consuming or vice versa, recalc
    if (old_status in ATTENDED_STATUSES) != (new_status in ATTENDED_STATUSES):
        consumed, delta = recalc_sessions_consumed(enrollment)
        if delta:
            # delta > 0 => consumed more sessions
            if delta > 0:
                BillingEntry.objects.create(
                    enrollment=enrollment,
                    entry_type=BillingEntry.EntryType.CONSUME,
                    sessions=-delta,
                    unit_price=int(enrollment.fee_per_session or 0),
                    amount=delta * int(enrollment.fee_per_session or 0),
                    note=f"Consume by attendance session {instance.session_id}",
                )
            else:
                BillingEntry.objects.create(
                    enrollment=enrollment,
                    entry_type=BillingEntry.EntryType.ADJUST,
                    sessions=-delta, 
                    unit_price=int(enrollment.fee_per_session or 0),
                    amount=delta * int(enrollment.fee_per_session or 0),
                    note=f"Adjust by attendance change session {instance.session_id}",
                )
        auto_update_status(enrollment)

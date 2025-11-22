from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError

from apps.attendance.models import Attendance
from apps.students.models import StudentProduct
from apps.rewards import services
from apps.rewards.models import SessionPointEventType


@receiver(post_save, sender=Attendance)
def award_attendance_point(sender, instance, created, **kwargs):
    try:
        if instance.status != "P":
            return
        session = getattr(instance, "session", None)
        if not session:
            return
        services.award_session_point(
            student=instance.student,
            session=session,
            event_type=SessionPointEventType.ATTENDANCE,
            reason=f"Đi học đúng giờ - Buổi {getattr(session, 'index', '')}",
            delta=1,
            allow_duplicate=False,
        )
    except ValidationError:
        return
    except Exception:
        return


@receiver(post_save, sender=StudentProduct)
def award_product_point(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        session = getattr(instance, "session", None)
        if not session:
            return
        services.award_session_point(
            student=instance.student,
            session=session,
            event_type=SessionPointEventType.PRODUCT,
            reason=f"Sản phẩm buổi {getattr(session, 'index', '')}",
            delta=1,
            allow_duplicate=False,
        )
    except ValidationError:
        return
    except Exception:
        return

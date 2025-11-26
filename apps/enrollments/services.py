from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.attendance.models import Attendance
from apps.billing.models import BillingEntry, Discount
from apps.classes.models import Class
from apps.enrollments.models import Enrollment, EnrollmentStatus, EnrollmentStatusLog

ATTENDED_STATUSES = {"P", "L"}  


def sessions_from_payment(amount_paid: int, fee_per_session: int) -> int:
    if not amount_paid or not fee_per_session:
        return 0
    return int(amount_paid // fee_per_session)


def recalc_sessions_consumed(enrollment: Enrollment) -> tuple[int, int]:
    """
    Returns (consumed, delta). Delta = consumed - previous.
    """
    previous = enrollment.sessions_consumed
    consumed = (
        Attendance.objects.filter(
            session__klass=enrollment.klass,
            student=enrollment.student,
            status__in=ATTENDED_STATUSES,
        )
        .distinct()
        .count()
    )
    if previous != consumed:
        Enrollment.objects.filter(pk=enrollment.pk).update(sessions_consumed=consumed)
    return consumed, consumed - previous


def total_sessions_purchased(enrollment: Enrollment) -> int:
    base = max(enrollment.sessions_purchased, enrollment.sessions_from_payment)
    adj = (
        BillingEntry.objects.filter(enrollment=enrollment)
        .aggregate(v=Sum("sessions"))
        .get("v")
        or 0
    )
    return max(base + adj, 0)


def sessions_remaining(enrollment: Enrollment) -> int:
    total = total_sessions_purchased(enrollment)
    consumed, _ = recalc_sessions_consumed(enrollment)
    remaining = total - consumed
    return remaining if remaining > 0 else 0


def calculate_end_date(start_date: date | None, sessions_total: int, klass: Class | None) -> date | None:
    """
    Estimate end date based on class weekly schedule.
    If no schedule, assume daily sessions.
    """
    if not start_date or not sessions_total or sessions_total <= 0:
        return None

    schedule_days = []
    if klass:
        schedule_days = list(
            klass.weekly_schedules.order_by("day_of_week").values_list("day_of_week", flat=True)
        )
    schedule_set = set(schedule_days)

    current = start_date
    counted = 0
    guard = 0
    last_day = None
    while counted < sessions_total:
        guard += 1
        if guard > 5000:
            return None

        if schedule_set:
            if current.weekday() in schedule_set:
                counted += 1
                last_day = current
        else:
            counted += 1
            last_day = current
        current += timedelta(days=1)
    return last_day


def record_status_change(enrollment: Enrollment, new_status: str, *, reason: str, note: str = ""):
    if enrollment.status == new_status:
        return
    EnrollmentStatusLog.objects.create(
        enrollment=enrollment,
        old_status=enrollment.status,
        new_status=new_status,
        reason=reason,
        note=note,
    )
    enrollment.status = new_status


def auto_update_status(
    enrollment: Enrollment,
    today: date | None = None,
    *,
    force_recalculate_end_date: bool = False,
) -> bool:
    """
    Auto update enrollment:
    - If remaining sessions <= 0 -> CANCELLED.
    - If end_date is past -> CANCELLED.
    - If end_date missing but can be projected -> set it.
    - If force_recalculate_end_date=True, always refresh projected end date.
    Returns True if updated.
    """
    updated = False
    today = today or date.today()

    total = total_sessions_purchased(enrollment)
    remaining = sessions_remaining(enrollment) if total else enrollment.sessions_remaining

    if remaining <= 0 and enrollment.status != EnrollmentStatus.CANCELLED:
        record_status_change(enrollment, EnrollmentStatus.CANCELLED, reason="AUTO_END_OF_SESSIONS")
        enrollment.end_date = enrollment.end_date or today
        enrollment.active = False
        enrollment.save(update_fields=["status", "end_date", "active"])
        updated = True

    if enrollment.end_date and enrollment.end_date < today and enrollment.status != EnrollmentStatus.CANCELLED:
        record_status_change(enrollment, EnrollmentStatus.CANCELLED, reason="AUTO_PAST_END_DATE")
        enrollment.active = False
        enrollment.save(update_fields=["status", "active"])
        updated = True

    projected = calculate_end_date(enrollment.start_date, total, enrollment.klass)
    if projected and (force_recalculate_end_date or projected != enrollment.end_date):
        enrollment.end_date = projected
        enrollment.save(update_fields=["end_date"])
        updated = True
    elif force_recalculate_end_date and not projected and enrollment.end_date:
        enrollment.end_date = None
        enrollment.save(update_fields=["end_date"])
        updated = True

    return updated


def apply_discount(discount: Discount | None, unit_price: int, sessions: int) -> tuple[int, int]:
    """
    Returns (discount_amount, unit_price_after_discount)
    """
    if not discount or not discount.active:
        return 0, unit_price
    today = date.today()
    if discount.start_date and discount.start_date > today:
        return 0, unit_price
    if discount.end_date and discount.end_date < today:
        return 0, unit_price

    base_amount = unit_price * sessions
    percent_val = (discount.percent or 0) * base_amount / 100
    fixed_val = discount.amount or 0
    total_discount = int(percent_val + fixed_val)
    if discount.max_amount:
        total_discount = min(total_discount, int(discount.max_amount))
    discount_amount = max(total_discount, 0)
    new_unit_price = unit_price
    if sessions > 0:
        effective_total = max(base_amount - discount_amount, 0)
        new_unit_price = effective_total // sessions if sessions else unit_price
    return discount_amount, new_unit_price


def create_purchase_entry(
    enrollment: Enrollment,
    *,
    discount: Discount | None = None,
    note: str = "Auto from enrollment",
    force: bool = False,
):
    """
    Create a purchase entry based on enrollment's purchased/payment fields.
    Skip if sessions <= 0 or a purchase entry already exists (unless force=True).
    """
    sessions = max(enrollment.sessions_purchased, enrollment.sessions_from_payment)
    if sessions <= 0:
        return None
    if not force and BillingEntry.objects.filter(
        enrollment=enrollment, entry_type=BillingEntry.EntryType.PURCHASE
    ).exists():
        return None
    unit_price = int(enrollment.fee_per_session or 0)
    discount_amount, new_unit_price = apply_discount(discount, unit_price, sessions)
    amount = max(new_unit_price * sessions, 0)
    return BillingEntry.objects.create(
        enrollment=enrollment,
        entry_type=BillingEntry.EntryType.PURCHASE,
        sessions=sessions,
        unit_price=new_unit_price,
        discount=discount,
        discount_amount=discount_amount,
        amount=amount,
        note=note,
    )


def transfer_enrollment_funds(
    source: Enrollment,
    target: Enrollment,
    amount: Decimal,
    *,
    actor=None,
    note: str = "",
):
    if source.pk == target.pk:
        raise ValueError("Nguồn và đích phải khác nhau.")
    amount = Decimal(amount or 0)
    if amount <= 0:
        raise ValueError("Số tiền chuyển phải lớn hơn 0.")
    remaining = Decimal(source.remaining_amount or 0)
    if amount > remaining:
        raise ValueError("Số tiền chuyển vượt quá số dư hiện có.")

    fee_source = Decimal(source.fee_per_session or 0)
    if fee_source <= 0:
        raise ValueError("Ghi danh nguồn chưa thiết lập đơn giá.")

    sessions_decimal = amount / fee_source
    if sessions_decimal != sessions_decimal.to_integral_value():
        raise ValueError("Số tiền phải chia hết cho đơn giá nguồn.")
    sessions = int(sessions_decimal)
    if sessions <= 0:
        raise ValueError("Số buổi chuyển phải lớn hơn 0.")

    auto_note = f"Chuyển phí sang {target.student} - {target.klass.code}"
    if note:
        auto_note = f"{auto_note}. Ghi chú: {note}"
    actor_label = f" bởi {actor}" if actor else ""

    with transaction.atomic():
        BillingEntry.objects.create(
            enrollment=source,
            entry_type=BillingEntry.EntryType.ADJUST,
            sessions=-sessions,
            unit_price=fee_source,
            amount=-amount,
            note=f"{auto_note}{actor_label}",
        )
        BillingEntry.objects.create(
            enrollment=target,
            entry_type=BillingEntry.EntryType.ADJUST,
            sessions=sessions,
            unit_price=fee_source,
            amount=amount,
            note=f"Nhận chuyển phí từ {source.student} - {source.klass.code}{actor_label}. {note}".strip(),
        )

        auto_update_status(source, force_recalculate_end_date=True)
        auto_update_status(target, force_recalculate_end_date=True)

    return sessions

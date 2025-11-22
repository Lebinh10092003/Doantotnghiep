from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction

from apps.accounts.models import User
from apps.rewards.models import (
    PointAccount,
    RedemptionRequest,
    RedemptionStatus,
    RewardItem,
    RewardTransaction,
    SessionPointEvent,
    SessionPointEventType,
)


def _ensure_account(student: User) -> PointAccount:
    return PointAccount.get_or_create_for_student(student)


@transaction.atomic
def award_points(
    *,
    student: User,
    delta: int,
    reason: str = "",
    item: RewardItem | None = None,
    created_by: User | None = None,
    session=None,
) -> RewardTransaction:
    if delta <= 0:
        raise ValidationError("Số điểm cộng phải lớn hơn 0.")
    account = _ensure_account(student)
    account.adjust_balance(delta)
    return RewardTransaction.objects.create(
        student=student,
        delta=delta,
        reason=reason or "Thưởng điểm",
        item=item,
        session=session,
    )


@transaction.atomic
def submit_redemption_request(*, student: User, item: RewardItem, quantity: int, note: str = "") -> RedemptionRequest:
    if quantity <= 0:
        raise ValidationError("Số lượng phải lớn hơn 0.")
    if not item.is_active:
        raise ValidationError("Phần quà này tạm khóa.")
    if item.stock < quantity:
        raise ValidationError("Không đủ tồn kho cho phần quà này.")
    account = _ensure_account(student)
    total_cost = item.cost * quantity
    account.refresh_from_db()
    if account.balance < total_cost:
        raise ValidationError("Bạn chưa đủ điểm để đổi quà này.")

    req = RedemptionRequest.objects.create(
        student=student,
        item=item,
        quantity=quantity,
        cost_snapshot=item.cost,
        note=note,
    )
    return req


def _deduct_points_for_request(req: RedemptionRequest):
    account = _ensure_account(req.student)
    total_cost = req.total_cost
    account.refresh_from_db()
    if account.balance < total_cost:
        raise ValidationError("Không đủ điểm để duyệt yêu cầu.")
    account.adjust_balance(-total_cost)
    RewardTransaction.objects.create(
        student=req.student,
        delta=-total_cost,
        reason=f"Đổi quà: {req.item.name}",
        item=req.item,
        redemption=req,
    )


def _refund_points_for_request(req: RedemptionRequest):
    account = _ensure_account(req.student)
    total_cost = req.total_cost
    account.adjust_balance(total_cost)
    RewardTransaction.objects.create(
        student=req.student,
        delta=total_cost,
        reason=f"Hoàn điểm đổi quà: {req.item.name}",
        item=req.item,
        redemption=req,
    )


@transaction.atomic
def approve_redemption_request(*, req: RedemptionRequest, approver: User, note: str = "") -> RedemptionRequest:
    if req.status not in (RedemptionStatus.PENDING,):
        raise ValidationError("Chỉ duyệt được yêu cầu đang chờ.")
    req.refresh_from_db()
    item = req.item
    if not item.is_active:
        raise ValidationError("Phần quà đã bị khóa.")
    if item.stock < req.quantity:
        raise ValidationError("Không đủ tồn kho để duyệt.")

    _deduct_points_for_request(req)
    item.stock -= req.quantity
    item.save(update_fields=["stock"])

    req.status = RedemptionStatus.APPROVED
    if note:
        req.note = note
    req.approved_by = approver
    req.save(update_fields=["status", "note", "approved_by", "updated_at"])
    return req


@transaction.atomic
def award_session_point(
    *,
    student: User,
    session,
    event_type: SessionPointEventType,
    reason: str,
    delta: int = 1,
    allow_duplicate: bool = False,
) -> SessionPointEvent:
    if not allow_duplicate:
        existed = SessionPointEvent.objects.filter(
            student=student, session=session, event_type=event_type
        ).exists()
        if existed:
            raise ValidationError("Đã cộng điểm cho buổi này.")
    txn = award_points(
        student=student,
        delta=delta,
        reason=reason,
        session=session,
    )
    return SessionPointEvent.objects.create(
        student=student,
        session=session,
        event_type=event_type,
        transaction=txn,
        note=reason,
    )


@transaction.atomic
def fulfill_redemption_request(*, req: RedemptionRequest, approver: User | None = None, note: str = "") -> RedemptionRequest:
    if req.status not in (RedemptionStatus.APPROVED,):
        raise ValidationError("Chỉ đánh dấu đã trao cho yêu cầu đã duyệt.")
    req.status = RedemptionStatus.FULFILLED
    if note:
        req.note = note
    if approver:
        req.approved_by = approver
    req.save(update_fields=["status", "note", "approved_by", "updated_at"])
    return req


@transaction.atomic
def reject_redemption_request(*, req: RedemptionRequest, approver: User, note: str = "") -> RedemptionRequest:
    if req.status not in (RedemptionStatus.PENDING, RedemptionStatus.APPROVED):
        raise ValidationError("Không thể từ chối yêu cầu ở trạng thái hiện tại.")
    if req.status == RedemptionStatus.APPROVED:
        # Đã trừ điểm và trừ kho; cần hoàn lại
        req.item.stock += req.quantity
        req.item.save(update_fields=["stock"])
        _refund_points_for_request(req)
    req.status = RedemptionStatus.REJECTED
    if note:
        req.note = note
    req.approved_by = approver
    req.save(update_fields=["status", "note", "approved_by", "updated_at"])
    return req


@transaction.atomic
def cancel_redemption_request(*, req: RedemptionRequest, actor: User, note: str = "") -> RedemptionRequest:
    if req.status not in (RedemptionStatus.PENDING, RedemptionStatus.APPROVED):
        raise ValidationError("Không thể hủy yêu cầu ở trạng thái hiện tại.")
    # Nếu đã duyệt thì hoàn lại
    if req.status == RedemptionStatus.APPROVED:
        req.item.stock += req.quantity
        req.item.save(update_fields=["stock"])
        _refund_points_for_request(req)
    req.status = RedemptionStatus.CANCELLED
    if note:
        req.note = note
    req.approved_by = actor
    req.save(update_fields=["status", "note", "approved_by", "updated_at"])
    return req

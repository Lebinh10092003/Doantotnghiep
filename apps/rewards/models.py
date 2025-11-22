from django.db import models, transaction
from steam_center.storages import MediaStorage
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class PointAccount(models.Model):
    student = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="point_account"
    )
    balance = models.IntegerField(default=0)

    @classmethod
    def get_or_create_for_student(cls, student):
        account, _ = cls.objects.get_or_create(student=student, defaults={"balance": 0})
        return account

    def adjust_balance(self, delta: int):
        with transaction.atomic():
            self.refresh_from_db()
            self.balance = models.F("balance") + delta
            self.save(update_fields=["balance"])
            self.refresh_from_db()
            return self.balance


    def __str__(self):
        return f"{self.student.username}: {self.balance} points"


class RewardItem(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(
        upload_to="reward_items/", 
        storage=MediaStorage(),
        blank=True, 
        null=True)
    cost = models.IntegerField()
    description = models.TextField(blank=True)
    stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)


    def __str__(self):
        return f"{self.name} ({self.cost} pts)"


class RewardTransaction(models.Model):
    student = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="point_transactions"
    )
    delta = models.IntegerField()
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    item = models.ForeignKey(
        RewardItem, null=True, blank=True, on_delete=models.SET_NULL
    )
    redemption = models.ForeignKey(
        "RedemptionRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    session = models.ForeignKey(
        "class_sessions.ClassSession",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reward_transactions",
    )


    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["student"]), models.Index(fields=["created_at"])]


    def __str__(self):
        return f"{self.student.username}: {self.delta} ({self.reason})"


class SessionPointEventType(models.TextChoices):
    ATTENDANCE = "ATTENDANCE", _("Điểm danh")
    PRODUCT = "PRODUCT", _("Sản phẩm")
    MANUAL = "MANUAL", _("Thủ công")


class SessionPointEvent(models.Model):
    student = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="session_point_events"
    )
    session = models.ForeignKey(
        "class_sessions.ClassSession",
        on_delete=models.CASCADE,
        related_name="point_events",
    )
    event_type = models.CharField(
        max_length=20, choices=SessionPointEventType.choices, db_index=True
    )
    transaction = models.ForeignKey(
        RewardTransaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="session_point_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = (("student", "session", "event_type"),)
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student"]),
            models.Index(fields=["session"]),
            models.Index(fields=["event_type"]),
        ]

    def __str__(self):
        return f"{self.student} - {self.session} - {self.event_type}"


class RedemptionStatus(models.TextChoices):
    PENDING = "PENDING", "Chờ duyệt"
    APPROVED = "APPROVED", "Đã duyệt"
    REJECTED = "REJECTED", "Từ chối"
    FULFILLED = "FULFILLED", "Đã trao"
    CANCELLED = "CANCELLED", "Đã hủy"


class RedemptionRequest(models.Model):
    student = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="redemption_requests"
    )
    item = models.ForeignKey(
        RewardItem, on_delete=models.PROTECT, related_name="redemption_requests"
    )
    quantity = models.PositiveIntegerField(default=1)
    cost_snapshot = models.IntegerField()
    status = models.CharField(
        max_length=20, choices=RedemptionStatus.choices, default=RedemptionStatus.PENDING
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_redemptions",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student"]),
            models.Index(fields=["item"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    @property
    def total_cost(self) -> int:
        return self.cost_snapshot * self.quantity

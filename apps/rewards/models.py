from django.db import models


class PointAccount(models.Model):
    student = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="point_account"
    )
    balance = models.IntegerField(default=0)


    def __str__(self):
        return f"{self.student.username}: {self.balance} points"


class RewardItem(models.Model):
    name = models.CharField(max_length=200)
    cost = models.IntegerField()


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


    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["student"]), models.Index(fields=["created_at"])]


    def __str__(self):
        return f"{self.student.username}: {self.delta} ({self.reason})"

from django.db import models
from apps.common.models import NamedModel
from steam_center.storages import MediaStorage


class Center(NamedModel):
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(max_length=254, blank=True)
    avatar = models.ImageField(
        upload_to="center_avatars/",
        storage=MediaStorage(),
        null=True,
        blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Room(models.Model):
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100)
    note = models.CharField(max_length=255, blank=True)


    class Meta:
        unique_together = (("center", "name"),)


    def __str__(self):
        return f"{self.center.name} - {self.name}"

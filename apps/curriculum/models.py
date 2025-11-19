from django.db import models
from apps.common.models import NamedModel
from steam_center.storages import MediaStorage


class Subject(NamedModel):
    avatar = models.ImageField(
        upload_to='subjects/avatars/',
        storage=MediaStorage(),
        blank=True, 
        null=True, 
        verbose_name="Ảnh đại diện")
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
    
    @property
    def avatar_url(self):
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return None


class Module(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="modules"
    )
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='modules/images/', 
        storage=MediaStorage(),
        blank=True, 
        null=True, 
        verbose_name="Ảnh minh họa")


    class Meta:
        unique_together = (("subject", "order"),)
        ordering = ["subject", "order"]


    def __str__(self):
        return f"{self.subject.name} - Học phần {self.order}: {self.title}"

    @property
    def image_url(self):
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        return None


class Lesson(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name="lessons")
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    objectives = models.TextField(blank=True)


    class Meta:
        unique_together = (("module", "order"),)
        ordering = ["module", "order"]


    def __str__(self):
        return f"{self.module.title} - Bài {self.order}: {self.title}"


class Lecture(models.Model):
    lesson = models.OneToOneField(
        Lesson, on_delete=models.CASCADE, related_name="lecture"
    )
    content = models.TextField(blank=True)
    file = models.FileField(
        upload_to="lectures/", 
        storage=MediaStorage(),
        blank=True, 
        null=True)
    video_url = models.URLField(blank=True, null=True)


    def __str__(self):
        return f"Bài giảng của {self.lesson.title}"


class Exercise(models.Model):
    lesson = models.OneToOneField(
        Lesson, on_delete=models.CASCADE, related_name="exercise"
    )
    description = models.TextField(blank=True)
    file = models.FileField(
        upload_to="exercises/", 
        storage=MediaStorage(),
        blank=True, 
        null=True)
    link_url = models.URLField(blank=True, null=True)
    difficulty = models.CharField(
        max_length=20,
        choices=[("easy", "Dễ"), ("medium", "Trung bình"), ("hard", "Khó")],
        default="medium",
    )


    def __str__(self):
        return f"Bài tập cho {self.lesson.title}"

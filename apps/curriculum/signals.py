from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import Lecture, Exercise


def _delete_field_file(file_field):
    try:
        if file_field and getattr(file_field, "name", None):
            # Xóa file khỏi storage mà không tác động lại tới model
            file_field.delete(save=False)
    except Exception:
        # Nuốt lỗi để không chặn các thao tác model
        pass


@receiver(post_delete, sender=Lecture)
def lecture_file_delete_on_model_delete(sender, instance: Lecture, **kwargs):
    _delete_field_file(getattr(instance, "file", None))


@receiver(pre_save, sender=Lecture)
def lecture_file_delete_on_change(sender, instance: Lecture, **kwargs):
    if not instance.pk:
        return
    try:
        old = Lecture.objects.get(pk=instance.pk)
    except Lecture.DoesNotExist:
        return

    old_file = getattr(old, "file", None)
    new_file = getattr(instance, "file", None)
    # Khi file bị xóa hoặc thay thế
    if (old_file and getattr(old_file, "name", None)) and (
        not new_file or getattr(new_file, "name", None) != getattr(old_file, "name", None)
    ):
        _delete_field_file(old_file)


@receiver(post_delete, sender=Exercise)
def exercise_file_delete_on_model_delete(sender, instance: Exercise, **kwargs):
    _delete_field_file(getattr(instance, "file", None))


@receiver(pre_save, sender=Exercise)
def exercise_file_delete_on_change(sender, instance: Exercise, **kwargs):
    if not instance.pk:
        return
    try:
        old = Exercise.objects.get(pk=instance.pk)
    except Exercise.DoesNotExist:
        return

    old_file = getattr(old, "file", None)
    new_file = getattr(instance, "file", None)
    if (old_file and getattr(old_file, "name", None)) and (
        not new_file or getattr(new_file, "name", None) != getattr(old_file, "name", None)
    ):
        _delete_field_file(old_file)


from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import User


def _delete_field_file(file_field):
    try:
        if file_field and getattr(file_field, "name", None):
            file_field.delete(save=False)
    except Exception:
        pass


@receiver(post_delete, sender=User)
def user_avatar_delete_on_model_delete(sender, instance: User, **kwargs):
    _delete_field_file(getattr(instance, "avatar", None))


@receiver(pre_save, sender=User)
def user_avatar_delete_on_change(sender, instance: User, **kwargs):
    if not instance.pk:
        return
    try:
        old = User.objects.get(pk=instance.pk)
    except User.DoesNotExist:
        return

    old_file = getattr(old, "avatar", None)
    new_file = getattr(instance, "avatar", None)
    if (old_file and getattr(old_file, "name", None)) and (
        not new_file or getattr(new_file, "name", None) != getattr(old_file, "name", None)
    ):
        _delete_field_file(old_file)


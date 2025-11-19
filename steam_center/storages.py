import os
from urllib.parse import quote

from django.core.exceptions import ImproperlyConfigured
from storages.backends.gcloud import GoogleCloudStorage


class MediaStorage(GoogleCloudStorage):
    """
    Firebase Cloud Storage backend for media files.
    The bucket name, ACL, and location can be configured through environment variables.
    """

    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET") or os.getenv("GS_BUCKET_NAME")
    default_acl = os.getenv("FIREBASE_DEFAULT_ACL", os.getenv("GS_DEFAULT_ACL", "publicRead"))
    file_overwrite = False
    location = os.getenv("FIREBASE_MEDIA_LOCATION", "media")

    def __init__(self, *args, **kwargs):
        bucket = kwargs.get("bucket_name") or self.bucket_name
        if not bucket:
            raise ImproperlyConfigured("FIREBASE_STORAGE_BUCKET must be set when using MediaStorage.")
        kwargs.setdefault("bucket_name", bucket)
        super().__init__(*args, **kwargs)

    def url(self, name, *args, **kwargs):
        normalized_name = self._normalize_name(name)
        encoded_name = quote(normalized_name, safe="")
        return f"https://firebasestorage.googleapis.com/v0/b/{self.bucket_name}/o/{encoded_name}?alt=media"

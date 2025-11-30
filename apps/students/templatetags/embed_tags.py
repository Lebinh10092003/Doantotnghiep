from urllib.parse import urlparse
import re
from html import escape

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


DEFAULT_ALLOWED = {
    "www.youtube.com",
    "youtube.com",
    "youtu.be",
    "player.vimeo.com",
    "itch.io",
    "www.itch.io",
    "itch.zone",
    "scratch.mit.edu",
    "itch.io/embed",
    "codepen.io",
}


def _is_allowed(src: str) -> bool:
    try:
        host = urlparse(src).netloc.lower()
    except Exception:
        return False
    allowed = set(getattr(settings, "ALLOWED_STUDENT_EMBED_HOSTS", DEFAULT_ALLOWED))
    # Some providers use subdomains; allow suffix match
    return any(host == a or host.endswith("." + a) for a in allowed)


@register.filter(name="safe_embed")
def safe_embed(embed_code: str) -> str:
    """
    Sanitize and enhance iframe embed so games are playable inline.
    - Allow only <iframe> and only from allowed hosts
    - Force responsive sizing and enable features (fullscreen, gamepad, etc.)
    """
    if not embed_code:
        return ""
    try:
        # Try BeautifulSoup if available for robustness
        blocked_src = None
        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(embed_code, "html.parser")
            iframe = soup.find("iframe")
            if iframe and iframe.get("src"):
                src = iframe.get("src")
                if not _is_allowed(src):
                    blocked_src = src
                    src = None  # mark as blocked
            else:
                return ""
        except Exception:
            # Fallback: regex the first iframe src
            m = re.search(r"<iframe[^>]*src=[\"']([^\"']+)[\"'][^>]*>", embed_code, re.I)
            if not m:
                return ""
            src = m.group(1)
            if not _is_allowed(src):
                blocked_src = src
                src = None

        features = [
            "accelerometer",
            "autoplay",
            "clipboard-write",
            "encrypted-media",
            "fullscreen",
            "gamepad",
            "gyroscope",
            "picture-in-picture",
            "xr-spatial-tracking",
        ]
        if src:
            return mark_safe(
                f'<iframe src="{escape(src)}" class="w-100 h-100" '
                f'allow="{"; ".join(features)}" allowfullscreen="true" '
                f'loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>'
            )
        if blocked_src:
            return mark_safe(
                f'<div class="small text-muted">Nguồn nhúng không được hỗ trợ. '
                f'<a href="{escape(blocked_src)}" target="_blank" rel="noopener">Mở liên kết</a></div>'
            )
        return ""
    except Exception:
        return ""

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode


def build_password_reset_link(user, request) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse(
        "accounts:password_reset_confirm",
        kwargs={"uidb64": uidb64, "token": token},
    )
    return request.build_absolute_uri(path)


def send_password_reset_email(user, request) -> bool:
    reset_link = build_password_reset_link(user, request)
    timeout = getattr(settings, "PASSWORD_RESET_TIMEOUT", 3600)
    recipient = user.preferred_email() or user.email
    if not recipient:
        return False
    context = {
        "user": user,
        "reset_link": reset_link,
        "timeout_hours": max(round(timeout / 3600), 1),
        "site_name": getattr(settings, "SITE_NAME", "EDS"),
        "support_email": getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
    }

    subject = render_to_string("emails/password_reset_subject.txt", context).strip()
    html_body = render_to_string("emails/password_reset_body.html", context)
    text_body = strip_tags(html_body)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)
    return True

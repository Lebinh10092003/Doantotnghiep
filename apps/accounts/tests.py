from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetFlowTests(TestCase):
	def setUp(self):
		cache.clear()
		self.user = get_user_model().objects.create_user(
			username="tester",
			email="tester@example.com",
			phone="0123456789",
			password="OldPass!234",
			is_active=True,
		)

	def test_request_password_reset_sends_email_for_existing_user(self):
		response = self.client.post(
			reverse("accounts:password_reset"),
			{"identifier": self.user.email},
			follow=False,
		)
		self.assertRedirects(response, reverse("accounts:password_reset_done"))
		self.assertEqual(len(mail.outbox), 1)
		email = mail.outbox[0]
		self.assertIn("Hướng dẫn đặt lại mật khẩu", email.subject)
		self.assertTrue(any("Đặt lại mật khẩu" in alt[0] for alt in email.alternatives))

	def test_request_password_reset_is_silent_for_unknown_user(self):
		response = self.client.post(
			reverse("accounts:password_reset"),
			{"identifier": "unknown@example.com"},
			follow=False,
		)
		self.assertRedirects(response, reverse("accounts:password_reset_done"))
		self.assertEqual(len(mail.outbox), 0)

	def test_password_reset_confirm_updates_password(self):
		uid = urlsafe_base64_encode(force_bytes(self.user.pk))
		token = default_token_generator.make_token(self.user)
		url = reverse("accounts:password_reset_confirm", kwargs={"uidb64": uid, "token": token})
		response = self.client.post(
			url,
			{"new_password1": "NewPass!234", "new_password2": "NewPass!234"},
			follow=False,
		)
		self.assertRedirects(response, reverse("accounts:password_reset_complete"))
		self.assertTrue(self.client.login(username="tester", password="NewPass!234"))

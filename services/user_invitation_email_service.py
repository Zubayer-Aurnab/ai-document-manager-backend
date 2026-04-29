"""HTML bodies and subjects for user invite / welcome (uses BrevoEmailService)."""
from __future__ import annotations

import html
from urllib.parse import quote

from flask import current_app

from services.brevo_email_service import BrevoEmailService


class UserInvitationEmailService:
    def __init__(self, mailer: BrevoEmailService | None = None):
        self._mailer = mailer or BrevoEmailService()

    def send_verification_email(self, *, to_email: str, full_name: str, raw_token: str) -> bool:
        base = current_app.config["FRONTEND_URL"].rstrip("/")
        # Link hits the SPA; token is only in query string on our origin.
        verify_url = f"{base}/verify-email?token={quote(raw_token, safe='')}"
        safe_name = html.escape(full_name)
        safe_email = html.escape(to_email)
        subject = "Verify your email to activate your account"
        body = f"""
<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;line-height:1.5;color:#111;">
  <p>Hi {safe_name},</p>
  <p>An administrator created an account for <strong>{safe_email}</strong> on Document Manager.</p>
  <p>Please confirm your email address within <strong>2 days</strong> using the button below. After verification,
  you will receive a separate email with your sign-in details.</p>
  <p style="margin:28px 0;">
    <a href="{verify_url}" style="background:#4f46e5;color:#fff;padding:12px 22px;border-radius:8px;
      text-decoration:none;display:inline-block;font-weight:600;">Verify email</a>
  </p>
  <p style="font-size:13px;color:#555;">If the button does not work, copy this link into your browser:<br/>
  <span style="word-break:break-all;">{html.escape(verify_url)}</span></p>
</body></html>
"""
        return self._mailer.send_html(
            to_email=to_email,
            to_name=full_name,
            subject=subject,
            html_content=body.strip(),
        )

    def send_welcome_email(self, *, to_email: str, full_name: str, plaintext_password: str) -> bool:
        safe_name = html.escape(full_name)
        safe_email = html.escape(to_email)
        safe_pw = html.escape(plaintext_password)
        base = current_app.config["FRONTEND_URL"].rstrip("/")
        signin_url = f"{base}/signin"
        subject = "Welcome — your account is ready"
        body = f"""
<!DOCTYPE html>
<html><body style="font-family:system-ui,sans-serif;line-height:1.5;color:#111;">
  <p>Hi {safe_name},</p>
  <p>Your email is verified. You can sign in with the credentials below:</p>
  <table style="margin:16px 0;border-collapse:collapse;">
    <tr><td style="padding:6px 12px;background:#f4f4f5;"><strong>Email</strong></td>
        <td style="padding:6px 12px;">{safe_email}</td></tr>
    <tr><td style="padding:6px 12px;background:#f4f4f5;"><strong>Password</strong></td>
        <td style="padding:6px 12px;font-family:monospace;">{safe_pw}</td></tr>
  </table>
  <p style="margin:24px 0;">
    <a href="{html.escape(signin_url)}" style="background:#059669;color:#fff;padding:12px 22px;border-radius:8px;
      text-decoration:none;display:inline-block;font-weight:600;">Sign in</a>
  </p>
  <p style="font-size:13px;color:#555;">For security, change your password after first login from account settings if available.</p>
</body></html>
"""
        return self._mailer.send_html(
            to_email=to_email,
            to_name=full_name,
            subject=subject,
            html_content=body.strip(),
        )

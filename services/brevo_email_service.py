"""Send transactional email via Brevo REST API (https://developers.brevo.com/)."""
from __future__ import annotations

import logging
from typing import Any

import requests
from flask import current_app

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class BrevoEmailService:
    def send_html(
        self,
        *,
        to_email: str,
        to_name: str | None,
        subject: str,
        html_content: str,
    ) -> bool:
        api_key = current_app.config.get("BREVO_API_KEY")
        sender_email = current_app.config.get("BREVO_SENDER_EMAIL")
        sender_name = current_app.config.get("BREVO_SENDER_NAME", "Document Manager")

        if not api_key or not sender_email:
            logger.warning(
                "Brevo not configured (BREVO_API_KEY / BREVO_SENDER_EMAIL); email to %s not sent.",
                to_email,
            )
            return False

        payload: dict[str, Any] = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": to_email, "name": to_name or to_email.split("@", 1)[0]}],
            "subject": subject,
            "htmlContent": html_content,
        }

        try:
            resp = requests.post(
                BREVO_API_URL,
                json=payload,
                headers={"accept": "application/json", "api-key": api_key, "content-type": "application/json"},
                timeout=30,
            )
            if resp.status_code >= 400:
                logger.error("Brevo API error %s: %s", resp.status_code, resp.text[:500])
                return False
            return True
        except requests.RequestException as e:
            logger.exception("Brevo request failed: %s", e)
            return False

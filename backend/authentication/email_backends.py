import json
import logging
from urllib import error, request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMultiAlternatives

logger = logging.getLogger(__name__)


class ResendApiEmailBackend(BaseEmailBackend):
    api_url = "https://api.resend.com/emails"
    user_agent = "MacroMapper/1.0 (+https://macromapper.judeandrewalaba.com)"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = settings.EMAIL_HOST_PASSWORD
        if not api_key:
            logger.error(
                "Resend API email delivery failed: DJANGO_EMAIL_HOST_KEY is missing or empty."
            )
            if self.fail_silently:
                return 0
            raise ValueError("DJANGO_EMAIL_HOST_KEY is required for Resend API email.")

        sent_count = 0
        for message in email_messages:
            try:
                self._send_message(message, api_key)
            except error.HTTPError as exc:
                logger.error(
                    "Resend API email delivery failed with HTTP %s: %s",
                    exc.code,
                    exc.reason or "HTTP Error",
                    exc_info=True,
                )
                if not self.fail_silently:
                    raise
            except Exception as exc:
                logger.error(
                    "Resend API email delivery failed due to network/system error (%s): %s",
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )
                if not self.fail_silently:
                    raise
            else:
                sent_count += 1
        return sent_count

    def _send_message(self, message, api_key):
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": message.to,
            "subject": message.subject,
            "text": message.body,
        }
        if message.cc:
            payload["cc"] = message.cc
        if message.bcc:
            payload["bcc"] = message.bcc

        html_body = self._get_html_body(message)
        if html_body:
            payload["html"] = html_body

        http_request = request.Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
            method="POST",
        )
        timeout = getattr(settings, "EMAIL_TIMEOUT", None)
        if timeout is None or not isinstance(timeout, (int, float)) or timeout <= 0:
            timeout = 10

        with request.urlopen(http_request, timeout=timeout) as response:
            status = response.getcode()
            if 200 <= status < 300:
                return

            response_body = response.read().decode("utf-8", errors="replace")
            raise error.HTTPError(
                self.api_url,
                status,
                response_body,
                response.headers,
                None,
            )

    def _get_html_body(self, message):
        if not isinstance(message, EmailMultiAlternatives):
            return None

        for content, mimetype in message.alternatives:
            if mimetype == "text/html":
                return content

        return None

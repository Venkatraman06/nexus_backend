import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _brand_context(extra: dict | None = None) -> dict:
    ctx = {
        "company_name": settings.COMPANY_NAME,
        "company_short_name": settings.COMPANY_SHORT_NAME,
        "support_email": settings.SUPPORT_EMAIL,
        "app_url": settings.FRONTEND_APP_URL,
    }
    if extra:
        ctx.update(extra)
    return ctx


def send_branded_email(*, to: str, subject: str, template: str, context: dict) -> bool:
    try:
        html = render_to_string(template, _brand_context(context))
        msg = EmailMultiAlternatives(
            subject=subject,
            body=_html_to_plain(html),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to],
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        return False


def send_password_reset_otp_email(*, to: str, full_name: str, otp: str) -> bool:
    return send_branded_email(
        to=to,
        subject=f"{settings.COMPANY_SHORT_NAME} — Password Reset Verification Code",
        template="emails/reset_otp.html",
        context={
            "full_name": full_name,
            "otp_code": otp,
            "expiry_minutes": settings.OTP_EXPIRY_MINUTES,
        },
    )


def send_welcome_onboard_email(
    *,
    to: str,
    full_name: str,
    username: str,
    reset_link: str,
) -> bool:
    return send_branded_email(
        to=to,
        subject=f"Welcome to {settings.COMPANY_NAME} — Set Up Your Account",
        template="emails/welcome_onboard.html",
        context={
            "full_name": full_name,
            "username": username,
            "reset_link": reset_link,
        },
    )


def _html_to_plain(html: str) -> str:
    import re

    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()

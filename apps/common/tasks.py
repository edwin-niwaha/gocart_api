from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_contact_email_task(self, name: str, email: str, message: str):

    context = {
        "name": name,
        "email": email,
        "message": message,
        "shop_name": "GoCart",
        "support_email": settings.EMAIL_HOST_USER,
    }

    # =========================
    # 1. EMAIL TO ADMIN
    # =========================
    admin_subject = f"New support message from {name}"

    admin_html = render_to_string("contact_emails/contact_email.html", context)

    admin_email = EmailMultiAlternatives(
        subject=admin_subject,
        body="New message received",  # fallback text
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.EMAIL_HOST_USER],
    )
    admin_email.attach_alternative(admin_html, "text/html")
    admin_email.send()


    # =========================
    # 2. EMAIL TO USER (CONFIRMATION)
    # =========================
    user_subject = "We received your message"

    user_html = render_to_string("contact_emails/contact_confirmation.html", context)

    user_email = EmailMultiAlternatives(
        subject=user_subject,
        body="We received your message",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    user_email.attach_alternative(user_html, "text/html")
    user_email.send()

    return {"success": True}
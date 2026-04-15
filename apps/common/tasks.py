from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from apps.common.models import NewsletterSubscriber


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_contact_email_task(self, name: str, email: str, message: str, subject: str = "", tenant_slug: str = ""):
    if not getattr(settings, "ENABLE_EMAIL", True) or not getattr(settings, "DEFAULT_FROM_EMAIL", ""):
        return {"success": False, "reason": "email disabled"}

    support_email = getattr(settings, "EMAIL_HOST_USER", "") or settings.DEFAULT_FROM_EMAIL
    shop_name = tenant_slug or "GoCart"
    context = {
        "name": name,
        "email": email,
        "message": message,
        "subject": subject,
        "shop_name": shop_name,
        "support_email": support_email,
    }

    admin_subject = subject or f"New support message from {name}"
    admin_html = render_to_string("contact_emails/contact_email.html", context)
    admin_email = EmailMultiAlternatives(
        subject=admin_subject,
        body="New message received",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[support_email],
    )
    admin_email.attach_alternative(admin_html, "text/html")
    admin_email.send()

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


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_newsletter_confirmation_request_task(self, subscriber_id: int):
    subscriber = NewsletterSubscriber.objects.select_related("tenant").get(id=subscriber_id)

    frontend_base_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    confirm_url = f"{frontend_base_url}/newsletter/confirm?token={subscriber.confirmation_token}"

    context = {
        "email": subscriber.email,
        "shop_name": getattr(subscriber.tenant, "name", "GoCart") if subscriber.tenant else "GoCart",
        "confirm_url": confirm_url,
        "support_email": settings.SUPPORT_EMAIL,
    }

    subject = "Confirm your subscription"
    html_body = render_to_string(
        "newsletter_emails/subscription_confirm_request.html",
        context,
    )
    text_body = render_to_string(
        "newsletter_emails/subscription_confirm_request.txt",
        context,
    )

    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[subscriber.email],
    )
    email_message.attach_alternative(html_body, "text/html")
    email_message.send()

    return {"success": True}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_newsletter_subscription_confirmed_task(self, subscriber_id: int):
    subscriber = NewsletterSubscriber.objects.select_related("tenant").get(id=subscriber_id)

    context = {
        "email": subscriber.email,
        "shop_name": getattr(subscriber.tenant, "name", "GoCart") if subscriber.tenant else "GoCart",
        "support_email": settings.SUPPORT_EMAIL,
    }

    subject = "Subscription confirmed"
    html_body = render_to_string(
        "newsletter_emails/subscription_confirmed.html",
        context,
    )
    text_body = render_to_string(
        "newsletter_emails/subscription_confirmed.txt",
        context,
    )

    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[subscriber.email],
    )
    email_message.attach_alternative(html_body, "text/html")
    email_message.send()

    return {"success": True}
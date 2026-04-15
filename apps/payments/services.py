import random
import uuid
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
import logging
logger = logging.getLogger(__name__)

from apps.cart.models import CartItem
from .models import Payment


def generate_uuid() -> str:
    return str(uuid.uuid4())


def momo_headers(subscription_key: str, token: str | None = None, ref_id: str | None = None):
    headers = {
        "Ocp-Apim-Subscription-Key": subscription_key,
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Target-Environment"] = settings.MOMO_TARGET_ENVIRONMENT

    if ref_id:
        headers["X-Reference-Id"] = ref_id

    return headers


def create_access_token() -> str:
    url = f"{settings.MOMO_BASE_URL}/collection/token/"
    auth = requests.auth.HTTPBasicAuth(settings.MOMO_API_USER, settings.MOMO_API_KEY)
    headers = {
        "Ocp-Apim-Subscription-Key": settings.SUBSCRIPTION_KEY,
    }

    res = requests.post(url, headers=headers, auth=auth, timeout=30)
    res.raise_for_status()

    token = res.json().get("access_token")
    if not token:
        raise ValueError("MTN access token missing in response.")

    return token


def request_to_pay(*, phone: str, amount: Decimal, external_id: str | None = None) -> dict:
    access_token = create_access_token()
    transaction_id = generate_uuid()

    url = f"{settings.MOMO_BASE_URL}/collection/v1_0/requesttopay"
    headers = momo_headers(settings.SUBSCRIPTION_KEY, access_token, transaction_id)

    clean_phone = phone.replace("+", "").replace(" ", "")
    numeric_external_id = external_id or str(random.randint(10000000, 99999999))

    body = {
        "amount": str(int(amount)),
        "currency": settings.MOMO_CURRENCY,
        "externalId": numeric_external_id,
        "payer": {
            "partyIdType": "MSISDN",
            "partyId": clean_phone,
        },
        "payerMessage": "GoCart order payment",
        "payeeNote": "Thank you for using GoCart",
    }

    res = requests.post(url, json=body, headers=headers, timeout=30)

    data = {}
    try:
        data = res.json() if res.content else {}
    except Exception:
        data = {"raw": res.text}

    logger.warning(
        "MTN request_to_pay status=%s reference_id=%s response=%s",
        res.status_code,
        transaction_id,
        data,
    )

    return {
        "reference_id": transaction_id,
        "status_code": res.status_code,
        "data": data,
    }


def get_user_cart_total(user, tenant=None) -> Decimal:
    cart_items = CartItem.objects.select_related("variant").filter(cart__user=user)
    if tenant is not None:
        cart_items = cart_items.filter(variant__tenant=tenant)

    total = Decimal("0.00")
    for item in cart_items:
        unit_price = item.variant.price if item.variant and item.variant.price else Decimal("0.00")
        total += unit_price * item.quantity

    return total


def user_has_cart_items(user, tenant=None) -> bool:
    queryset = CartItem.objects.filter(cart__user=user)
    if tenant is not None:
        queryset = queryset.filter(variant__tenant=tenant)
    return queryset.exists()


def initiate_mtn_payment(*, user, phone_number: str, address, tenant=None) -> Payment:
    amount = get_user_cart_total(user, tenant)

    payment = Payment.objects.create(
        tenant=tenant,
        user=user,
        order=None,
        provider=Payment.Provider.MTN,
        amount=amount,
        currency=settings.MOMO_CURRENCY,
        phone_number=phone_number,
        status=Payment.Status.PENDING,
        provider_response={
            "address_id": address.id,
        },
    )

    result = request_to_pay(
        phone=phone_number,
        amount=amount,
        external_id=str(random.randint(10000000, 99999999)),
    )

    payment.external_id = result["reference_id"]
    payment.transaction_id = result["reference_id"]
    payment.provider_response = {
        **payment.provider_response,
        "initiate": result["data"],
        "initiate_status_code": result["status_code"],
        "address_id": address.id,
    }

    if result["status_code"] == 202:
        payment.status = Payment.Status.PROCESSING
        payment.save(
            update_fields=[
                "external_id",
                "transaction_id",
                "provider_response",
                "status",
                "updated_at",
            ]
        )
        return payment

    payment.status = Payment.Status.FAILED
    payment.save(
        update_fields=[
            "external_id",
            "transaction_id",
            "provider_response",
            "status",
            "updated_at",
        ]
    )

    raise ValidationError({
        "detail": "MTN payment request was not accepted.",
        "provider_response": result["data"],
        "provider_status_code": result["status_code"],
    })


def check_status(reference_id: str) -> dict:
    access_token = create_access_token()
    url = f"{settings.MOMO_BASE_URL}/collection/v1_0/requesttopay/{reference_id}"
    headers = momo_headers(settings.SUBSCRIPTION_KEY, token=access_token)

    res = requests.get(url, headers=headers, timeout=30)

    try:
        data = res.json() if res.content else {}
    except Exception:
        data = {"raw": res.text}

    logger.warning(
        "MTN check_status http_status=%s reference_id=%s response=%s",
        res.status_code,
        reference_id,
        data,
    )

    return {
        "http_status": res.status_code,
        "data": data,
    }


def refresh_mtn_payment_status(payment: Payment) -> Payment:
    if payment.provider != Payment.Provider.MTN or not payment.external_id:
        return payment

    result = check_status(payment.external_id)
    http_status = result.get("http_status")
    data = result.get("data", {})

    if http_status == 404:
        payment.status = Payment.Status.FAILED
        payment.provider_response = {
            **payment.provider_response,
            "status_check": data,
            "status_check_http_status": http_status,
        }
        payment.save(
            update_fields=[
                "status",
                "provider_response",
                "updated_at",
            ]
        )
        return payment

    if http_status >= 400: # type: ignore
        payment.provider_response = {
            **payment.provider_response,
            "status_check": data,
            "status_check_http_status": http_status,
        }
        payment.save(
            update_fields=[
                "provider_response",
                "updated_at",
            ]
        )
        return payment

    provider_status = str(data.get("status", "")).upper()

    financial_transaction_id = data.get("financialTransactionId")
    if financial_transaction_id:
        payment.transaction_id = str(financial_transaction_id)

    if provider_status == "SUCCESSFUL":
        payment.status = Payment.Status.PAID
        if not payment.paid_at:
            payment.paid_at = timezone.now()
    elif provider_status in {"FAILED", "REJECTED", "EXPIRED"}:
        payment.status = Payment.Status.FAILED
    else:
        payment.status = Payment.Status.PROCESSING

    payment.provider_response = {
        **payment.provider_response,
        "status_check": data,
        "status_check_http_status": http_status,
    }
    payment.save(
        update_fields=[
            "status",
            "provider_response",
            "transaction_id",
            "paid_at",
            "updated_at",
        ]
    )
    return payment
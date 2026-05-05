from django.urls import path

from .views import (
    CardInitiatePaymentView,
    MTNInitiatePaymentView,
    PaymentStatusView,
    FinalizePaidOrderView,
    UserPaymentListView,
)

urlpatterns = [
    path("", UserPaymentListView.as_view(), name="user-payments-list"),
    path("card/initiate/", CardInitiatePaymentView.as_view(), name="payments-card-initiate"),
    path("mtn/initiate/", MTNInitiatePaymentView.as_view(), name="payments-mtn-initiate"),
    path("<str:reference>/status/", PaymentStatusView.as_view(), name="payments-status"),
    path("<str:reference>/finalize-order/", FinalizePaidOrderView.as_view(), name="payments-finalize-order"),
]

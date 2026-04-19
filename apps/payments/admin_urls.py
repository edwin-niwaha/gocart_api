from django.urls import path

from .admin_views import AdminPaymentListView, AdminPaymentDetailView

urlpatterns = [
    path("", AdminPaymentListView.as_view(), name="admin-payments-list"),
    path("<int:pk>/", AdminPaymentDetailView.as_view(), name="admin-payments-detail"),
]
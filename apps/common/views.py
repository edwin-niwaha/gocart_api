from typing import cast

from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import ContactMessageSerializer
from .tasks import send_contact_email_task


class ContactMessageViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = cast(dict[str, str], serializer.validated_data)

        send_contact_email_task.delay(
            name=validated_data["name"],
            email=validated_data["email"],
            message=validated_data["message"],
        )

        return Response(
            {"detail": "Message queued successfully."},
            status=status.HTTP_201_CREATED,
        )
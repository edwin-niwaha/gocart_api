from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from rest_framework import serializers


class DashboardSummaryQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    low_stock_threshold = serializers.IntegerField(
        required=False,
        min_value=0,
        max_value=100000,
        default=5,
    )

    def _tenant_timezone(self):
        tenant = self.context.get("tenant")
        timezone_name = getattr(tenant, "timezone", "") or timezone.get_current_timezone_name()
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return timezone.get_current_timezone()

    def validate(self, attrs):
        today = timezone.localdate()
        date_from = attrs.get("date_from") or (today - timedelta(days=30))
        date_to = attrs.get("date_to") or today

        if date_from > date_to:
            raise serializers.ValidationError(
                {"date_from": "date_from must be on or before date_to."}
            )

        if (date_to - date_from).days > 366:
            raise serializers.ValidationError(
                {"date_to": "Dashboard ranges cannot exceed 366 days."}
            )

        current_tz = self._tenant_timezone()
        attrs["start_at"] = timezone.make_aware(
            datetime.combine(date_from, time.min),
            current_tz,
        )
        attrs["end_at"] = timezone.make_aware(
            datetime.combine(date_to, time.max),
            current_tz,
        )
        attrs["date_from"] = date_from
        attrs["date_to"] = date_to
        return attrs

from __future__ import annotations

from uuid import uuid4


class RequestIDMiddleware:
    header_name = "HTTP_X_REQUEST_ID"
    response_header = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = (request.META.get(self.header_name) or "").strip()
        if not request_id or len(request_id) > 128:
            request_id = uuid4().hex

        request.id = request_id
        response = self.get_response(request)
        response[self.response_header] = request_id
        return response

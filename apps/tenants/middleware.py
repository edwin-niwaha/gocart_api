from django.http import JsonResponse

from .utils import TenantResolutionError, resolve_tenant_from_request


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            request.tenant = resolve_tenant_from_request(request)
        except TenantResolutionError as exc:
            request.tenant = None
            return JsonResponse(
                {
                    "detail": str(exc),
                    "errors": {},
                    "code": "tenant_not_found",
                },
                status=404,
            )

        response = self.get_response(request)
        if getattr(request, "tenant", None):
            response["X-Tenant-Slug"] = request.tenant.slug
        return response

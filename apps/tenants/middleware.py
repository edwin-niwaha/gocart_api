from .utils import resolve_tenant_from_request


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = resolve_tenant_from_request(request)
        response = self.get_response(request)
        if getattr(request, "tenant", None):
            response["X-Tenant-Slug"] = request.tenant.slug
        return response

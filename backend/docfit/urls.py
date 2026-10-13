from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, HttpResponse, JsonResponse
from django.urls import include, path, re_path
from django.views.decorators.csrf import ensure_csrf_cookie

admin.site.site_header = "DocFit admin"
admin.site.site_title = "DocFit admin"


def health(request):
    return JsonResponse({"ok": True})


@ensure_csrf_cookie
def spa(request, *args, **kwargs):
    """Serve the React app for every non-API route."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return HttpResponse("Frontend not built. Run `npm run build` in frontend/, "
                            "or use the Vite dev server on http://localhost:5173.", status=503)
    resp = FileResponse(open(index, "rb"), content_type="text/html")
    resp["Cache-Control"] = "no-cache"
    return resp


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", health),
    path("api/", include("accounts.urls")),
    path("api/", include("billing.urls")),
    path("api/", include("jobs.urls")),
    re_path(r"^(?!api/|admin/|static/).*$", spa),
]

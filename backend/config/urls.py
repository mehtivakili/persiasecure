from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import PersianTokenObtainPairView
from apps.dashboard.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    # Health probe
    path("api/health", health, name="health"),
    # Auth (JWT) — custom view embeds the user profile + permissions in the response
    path("api/auth/token/", PersianTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # App routers
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.cameras.urls")),
    path("api/", include("apps.recordings.urls")),
    path("api/", include("apps.events.urls")),
    path("api/", include("apps.dashboard.urls")),
    # Phase 2
    path("api/", include("apps.analytics.urls")),
    path("api/", include("apps.access.urls")),
    path("api/", include("apps.maps.urls")),
    path("api/", include("apps.federation.urls")),
    path("api/", include("apps.evidence.urls")),
]

# Serve uploaded media (maps, snapshots, cardholder photos) from Django in
# all modes — in this deployment nginx proxies /media/ here, and the files
# live on the backend container's volume.
from django.conf import settings as _settings  # noqa: E402
from django.urls import re_path  # noqa: E402
from django.views.static import serve as _media_serve  # noqa: E402

urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        _media_serve,
        {"document_root": _settings.MEDIA_ROOT},
    ),
]

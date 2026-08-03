from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("maps", views.SiteMapViewSet, basename="sitemap")
router.register("map-markers", views.MapMarkerViewSet, basename="mapmarker")

urlpatterns = [path("", include(router.urls))]

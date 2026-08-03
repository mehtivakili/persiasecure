from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("cameras", views.CameraViewSet, basename="camera")
router.register("camera-groups", views.CameraGroupViewSet, basename="cameragroup")

urlpatterns = [
    path("cameras/brands", views.camera_brands, name="camera-brands"),
    path("cameras/onvif/discover", views.onvif_discover, name="onvif-discover"),
    path("cameras/onvif/probe", views.onvif_probe, name="onvif-probe"),
    path("", include(router.urls)),
]

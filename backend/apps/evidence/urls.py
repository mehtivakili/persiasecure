from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("evidence-cases", views.EvidenceCaseViewSet, basename="evidencecase")

urlpatterns = [path("", include(router.urls))]

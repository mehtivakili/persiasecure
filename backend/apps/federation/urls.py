from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("federated-servers", views.FederatedServerViewSet, basename="federatedserver")

urlpatterns = [path("", include(router.urls))]

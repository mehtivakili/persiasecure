from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("doors", views.DoorViewSet, basename="door")
router.register("cardholders", views.CardholderViewSet, basename="cardholder")
router.register("credentials", views.CredentialViewSet, basename="credential")
router.register("access-rules", views.AccessRuleViewSet, basename="accessrule")
router.register("access-events", views.AccessEventViewSet, basename="accessevent")

urlpatterns = [path("", include(router.urls))]

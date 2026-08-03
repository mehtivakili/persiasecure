"""Reusable DRF permission classes for VMS RBAC."""
from rest_framework.permissions import BasePermission


class HasVmsPermission(BasePermission):
    """
    Checks a codename declared on the view as `required_perm`.
    Superusers always pass. Read-only (GET/HEAD/OPTIONS) can declare a
    separate `required_perm_read`.
    """

    message = "شما دسترسی لازم برای این عملیات را ندارید."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if request.method in ("GET", "HEAD", "OPTIONS"):
            codename = getattr(view, "required_perm_read", None) or getattr(
                view, "required_perm", None
            )
        else:
            codename = getattr(view, "required_perm", None)
        if not codename:
            return True
        return user.has_vms_perm(codename)


class OrgScopedQuerysetMixin:
    """Limit a ViewSet queryset to the requesting user's organization."""

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(organization=user.organization)

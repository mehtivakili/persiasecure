from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuditLog, Organization, Role, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    search_fields = ("name", "slug")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "is_system")
    list_filter = ("organization", "is_system")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("PersianSecure", {"fields": ("organization", "role", "display_name", "phone")}),
    )
    list_display = ("username", "email", "organization", "role", "is_active")
    list_filter = ("organization", "role", "is_active", "is_superuser")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "target", "ip", "created_at")
    list_filter = ("action",)
    search_fields = ("action", "target")

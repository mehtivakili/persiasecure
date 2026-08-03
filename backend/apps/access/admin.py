from django.contrib import admin

from .models import AccessEvent, AccessRule, Cardholder, Credential, Door


class CredentialInline(admin.TabularInline):
    model = Credential
    extra = 1


@admin.register(Door)
class DoorAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "state", "camera")
    list_filter = ("organization", "state")


@admin.register(Cardholder)
class CardholderAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "employee_id", "active")
    inlines = [CredentialInline]


@admin.register(AccessRule)
class AccessRuleAdmin(admin.ModelAdmin):
    list_display = ("door", "cardholder", "allowed")


@admin.register(AccessEvent)
class AccessEventAdmin(admin.ModelAdmin):
    list_display = ("door", "cardholder", "decision", "reason", "ts")
    list_filter = ("decision",)

from django.contrib import admin

from .models import CustodyLog, EvidenceCase, EvidenceItem


class ItemInline(admin.TabularInline):
    model = EvidenceItem
    extra = 0


class CustodyInline(admin.TabularInline):
    model = CustodyLog
    extra = 0


@admin.register(EvidenceCase)
class EvidenceCaseAdmin(admin.ModelAdmin):
    list_display = ("case_number", "title", "status", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("case_number", "title")
    inlines = [ItemInline, CustodyInline]

from django.contrib import admin

from .models import MapMarker, SiteMap


class MarkerInline(admin.TabularInline):
    model = MapMarker
    extra = 0


@admin.register(SiteMap)
class SiteMapAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "order")
    inlines = [MarkerInline]

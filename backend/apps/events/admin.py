from django.contrib import admin

from .models import Bookmark, Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("type", "severity", "camera", "ts", "acknowledged", "cleared")
    list_filter = ("type", "severity", "acknowledged", "cleared")
    date_hierarchy = "ts"


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("camera", "note", "start", "user")

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from apps.accounts.models import log_action
from apps.accounts.permissions import HasVmsPermission

from . import notify
from .models import AutomationRule, Bookmark, Event, EventComment, NotificationSettings
from .serializers import (
    AutomationRuleSerializer,
    BookmarkSerializer,
    EventCommentSerializer,
    EventSerializer,
    NotificationSettingsSerializer,
)
from .utils import broadcast_event


@api_view(["GET", "PUT"])
@permission_classes([HasVmsPermission])
def notification_settings(request):
    """Get/update the org's notification provider + recipient phone numbers."""
    if not request.user.has_vms_perm("settings.manage"):
        return Response({"detail": "عدم دسترسی به تنظیمات."}, status=403)
    org = request.user.organization
    if org is None:
        return Response({"detail": "سازمانی برای کاربر ثبت نشده است."}, status=400)
    obj, _ = NotificationSettings.objects.get_or_create(organization=org)
    if request.method == "PUT":
        ser = NotificationSettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        log_action(request, "settings.notifications.update")
        return Response(ser.data)
    return Response(NotificationSettingsSerializer(obj).data)


@api_view(["POST"])
@permission_classes([HasVmsPermission])
def notification_test(request):
    """Send a test SMS/call using the org's saved config. Body: {phone, channel}."""
    if not request.user.has_vms_perm("settings.manage"):
        return Response({"detail": "عدم دسترسی."}, status=403)
    phone = request.data.get("phone")
    if not phone:
        return Response({"detail": "شماره تلفن الزامی است."}, status=400)
    channel = request.data.get("channel", "sms")
    conf = notify.org_conf(request.user.organization)
    message = "پیام آزمایشی پرشین‌سکیور — سامانه اعلان‌ها فعال است."
    if channel == "call":
        ok = notify.voice_call(phone, message, conf=conf)
    else:
        ok = notify.send_sms(phone, message, conf=conf)
    return Response({"ok": ok, "provider": conf.get("PROVIDER", "console")})


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [HasVmsPermission]
    required_perm_read = "event.view"
    required_perm = "event.ack"
    filterset_fields = ["camera", "type", "severity", "acknowledged", "cleared"]
    ordering_fields = ["ts", "severity"]

    def get_queryset(self):
        qs = Event.objects.select_related("camera", "ack_by", "assigned_to", "clip")
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        # Investigation filters (Phase 5).
        params = self.request.query_params
        if q := params.get("q"):
            qs = qs.filter(Q(type__icontains=q) | Q(camera__name__icontains=q))
        if after := parse_datetime(params.get("after") or ""):
            qs = qs.filter(ts__gte=after)
        if before := parse_datetime(params.get("before") or ""):
            qs = qs.filter(ts__lte=before)
        has_clip = params.get("has_clip")
        if has_clip in ("true", "1"):
            qs = qs.filter(clip__isnull=False)
        elif has_clip in ("false", "0"):
            qs = qs.filter(clip__isnull=True)
        if clip_status := params.get("clip_status"):
            qs = qs.filter(clip__status=clip_status)
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        event = serializer.save(
            organization=user.organization, type="manual"
        )
        # The Event post_save signal queues an event clip when the camera is
        # recording (Phase 3); manual events are a convenient test trigger.
        broadcast_event(event)

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        event = self.get_object()
        event.acknowledged = True
        event.ack_by = request.user
        event.ack_at = timezone.now()
        event.save(update_fields=["acknowledged", "ack_by", "ack_at"])
        broadcast_event(event)
        log_action(request, "event.ack", event.id)
        return Response(EventSerializer(event).data)

    @action(detail=True, methods=["post"])
    def clear(self, request, pk=None):
        event = self.get_object()
        event.cleared = True
        if not event.acknowledged:
            event.acknowledged = True
            event.ack_by = request.user
            event.ack_at = timezone.now()
        event.save()
        broadcast_event(event)
        log_action(request, "event.clear", event.id)
        return Response(EventSerializer(event).data)

    @action(detail=False, methods=["post"])
    def acknowledge_all(self, request):
        qs = self.get_queryset().filter(acknowledged=False)
        count = qs.update(
            acknowledged=True, ack_by=request.user, ack_at=timezone.now()
        )
        log_action(request, "event.ack_all", count)
        return Response({"acknowledged": count})

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """Assign (or unassign, user=null) an operator to own the alarm."""
        from apps.accounts.models import User

        event = self.get_object()
        uid = request.data.get("user")
        if uid in (None, ""):
            event.assigned_to = None
        else:
            scoped = User.objects.all()
            if not request.user.is_superuser:
                scoped = scoped.filter(organization=request.user.organization)
            target = scoped.filter(id=uid).first()
            if target is None:
                return Response({"detail": "کاربر یافت نشد."}, status=400)
            event.assigned_to = target
        event.save(update_fields=["assigned_to"])
        broadcast_event(event)
        log_action(request, "event.assign", event.id, user=uid)
        return Response(EventSerializer(event).data)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        event = self.get_object()
        if request.method == "POST":
            text = (request.data.get("text") or "").strip()
            if not text:
                return Response({"detail": "متن یادداشت الزامی است."}, status=400)
            comment = EventComment.objects.create(
                event=event, user=request.user, text=text[:1000]
            )
            log_action(request, "event.comment", event.id)
            return Response(EventCommentSerializer(comment).data, status=201)
        return Response(
            EventCommentSerializer(event.comments.select_related("user"), many=True).data
        )

    @action(detail=True, methods=["get"])
    def related(self, request, pk=None):
        """Other events from the same camera within ±30 minutes."""
        event = self.get_object()
        if not event.camera_id:
            return Response([])
        window = timedelta(minutes=30)
        qs = Event.objects.select_related("camera", "clip").filter(
            camera_id=event.camera_id,
            ts__gte=event.ts - window,
            ts__lte=event.ts + window,
        ).exclude(id=event.id)
        if not request.user.is_superuser:
            qs = qs.filter(organization=request.user.organization)
        return Response(EventSerializer(qs[:20], many=True).data)

    @action(detail=True, methods=["post"])
    def report(self, request, pk=None):
        """
        Human validation of a (usually AI‑produced) event: mark it a false
        positive and/or validated. A confirmed false positive is auto‑cleared.
        """
        event = self.get_object()
        details = dict(event.details or {})
        if "false_positive" in request.data:
            details["false_positive"] = bool(request.data.get("false_positive"))
        if "validated" in request.data:
            details["validated"] = bool(request.data.get("validated"))
        event.details = details
        if details.get("false_positive"):
            event.cleared = True
            if not event.acknowledged:
                event.acknowledged = True
                event.ack_by = request.user
                event.ack_at = timezone.now()
        event.save()
        broadcast_event(event)
        log_action(
            request, "event.report", event.id,
            false_positive=details.get("false_positive"),
            validated=details.get("validated"),
        )
        return Response(EventSerializer(event).data)

    @action(detail=True, methods=["get"])
    def audit(self, request, pk=None):
        """Operator audit trail for this event (ack/clear/assign/comment/clip)."""
        from apps.accounts.models import AuditLog
        from apps.accounts.serializers import AuditLogSerializer

        event = self.get_object()
        qs = AuditLog.objects.filter(target=str(event.id))
        if not request.user.is_superuser:
            qs = qs.filter(organization=request.user.organization)
        return Response(AuditLogSerializer(qs.order_by("-created_at")[:50], many=True).data)


class AutomationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = AutomationRuleSerializer
    permission_classes = [HasVmsPermission]
    required_perm = "automation.manage"
    required_perm_read = "automation.manage"
    filterset_fields = ["enabled", "action", "event_type"]

    def get_queryset(self):
        qs = AutomationRule.objects.select_related("camera")
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(organization=user.organization)
        return qs

    def perform_create(self, serializer):
        rule = serializer.save(organization=self.request.user.organization)
        log_action(self.request, "automation.create", rule.name)

    def perform_update(self, serializer):
        rule = serializer.save()
        log_action(self.request, "automation.update", rule.name)

    def perform_destroy(self, instance):
        log_action(self.request, "automation.delete", instance.name)
        instance.delete()


class BookmarkViewSet(viewsets.ModelViewSet):
    serializer_class = BookmarkSerializer
    permission_classes = [HasVmsPermission]
    required_perm_read = "playback.view"
    required_perm = "playback.view"
    filterset_fields = ["camera"]

    def get_queryset(self):
        qs = Bookmark.objects.select_related("camera")
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(camera__organization=user.organization)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

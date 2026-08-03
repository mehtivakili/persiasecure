"""
CSV report exports (Genetec-style activity reports).

GET /api/reports/<kind>?after=ISO&before=ISO&camera=<id>
kinds: events | access | plates
Response: UTF-8 CSV (with BOM so Excel renders Persian correctly).
"""
import csv

from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes

from apps.accounts.permissions import HasVmsPermission


def _filters(request, qs, ts_field="ts", camera_field="camera"):
    params = request.query_params
    if after := params.get("after"):
        if dt := parse_datetime(after):
            qs = qs.filter(**{f"{ts_field}__gte": dt})
    if before := params.get("before"):
        if dt := parse_datetime(before):
            qs = qs.filter(**{f"{ts_field}__lte": dt})
    if camera := params.get("camera"):
        qs = qs.filter(**{camera_field: camera})
    return qs


def _csv_response(filename, header, rows):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp.write("﻿")  # BOM for Excel + Persian
    writer = csv.writer(resp)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return resp


class _ReportPerm(HasVmsPermission):
    pass


@api_view(["GET"])
@permission_classes([_ReportPerm])
def report(request, kind):
    user = request.user
    if not user.has_vms_perm("report.view"):
        from rest_framework.response import Response

        return Response({"detail": "عدم دسترسی گزارش‌گیری."}, status=403)

    org_filter = {} if user.is_superuser else {"organization": user.organization}

    if kind == "events":
        from apps.events.models import Event

        qs = _filters(request, Event.objects.filter(**org_filter).select_related("camera"))
        rows = (
            (e.ts.isoformat(), e.type, e.severity, e.camera.name if e.camera else "",
             "بله" if e.acknowledged else "خیر", "بله" if e.cleared else "خیر")
            for e in qs.order_by("-ts")[:10000]
        )
        return _csv_response(
            "events.csv",
            ["زمان", "نوع", "شدت", "دوربین", "تأییدشده", "رفع‌شده"],
            rows,
        )

    if kind == "access":
        from apps.access.models import AccessEvent

        qs = _filters(
            request,
            AccessEvent.objects.filter(**org_filter).select_related("door", "cardholder"),
            camera_field="door",
        )
        rows = (
            (a.ts.isoformat(), a.door.name, str(a.cardholder or ""), a.credential_value,
             a.get_decision_display(), a.reason)
            for a in qs.order_by("-ts")[:10000]
        )
        return _csv_response(
            "access.csv",
            ["زمان", "در", "دارنده کارت", "اعتبارنامه", "تصمیم", "دلیل"],
            rows,
        )

    if kind == "plates":
        from apps.analytics.models import PlateRead

        qs = _filters(request, PlateRead.objects.filter(**org_filter).select_related("camera"))
        rows = (
            (p.ts.isoformat(), p.plate, f"{p.confidence:.0f}", p.camera.name,
             "بله" if p.watchlist_hit else "خیر")
            for p in qs.order_by("-ts")[:10000]
        )
        return _csv_response(
            "plates.csv",
            ["زمان", "پلاک", "اطمینان", "دوربین", "فهرست تحت نظر"],
            rows,
        )

    from rest_framework.response import Response

    return Response({"detail": "نوع گزارش نامعتبر است."}, status=400)

"""Writes the provisioned Grafana dashboards (P23). Run after changing a panel:
    python infra/observe/grafana/make_dashboards.py
"""
import json
from pathlib import Path

OUT = Path(__file__).parent / "dashboards"
PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}


def stat(pid, title, expr, x, y, unit="none", decimals=None, thresholds=None, w=4):
    return {"id": pid, "type": "stat", "title": title, "datasource": PROM, "gridPos": {"x": x, "y": y, "w": w, "h": 4},
            "targets": [{"refId": "A", "expr": expr, "datasource": PROM}],
            "options": {"reduceOptions": {"calcs": ["lastNotNull"]}, "colorMode": "background", "textMode": "value"},
            "fieldConfig": {"defaults": {"unit": unit, **({"decimals": decimals} if decimals is not None else {}),
                                         "noValue": "—",
                                         "thresholds": {"mode": "absolute", "steps": thresholds or [{"color": "#0B5D66", "value": None}]}},
                            "overrides": []}}


def series(pid, title, targets, x, y, unit="none", w=12, h=8):
    return {"id": pid, "type": "timeseries", "title": title, "datasource": PROM, "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "targets": [{"refId": chr(65 + i), "expr": e, "legendFormat": lf, "datasource": PROM} for i, (e, lf) in enumerate(targets)],
            "fieldConfig": {"defaults": {"unit": unit}, "overrides": []}}


def board(uid, title, panels, templating=None):
    return {"uid": uid, "title": title, "schemaVersion": 39, "version": 1, "refresh": "30s", "time": {"from": "now-6h", "to": "now"},
            "tags": ["bhojango"], "panels": panels, "templating": {"list": templating or []}, "annotations": {"list": []}}


city = {"name": "city", "label": "City", "type": "query", "datasource": PROM, "query": "label_values(bhojango_orders_live, city)",
        "refresh": 2, "current": {"text": "IN-TG-HYD", "value": "IN-TG-HYD"}, "includeAll": False}
S = '{city="$city"}'
red_over = lambda v: [{"color": "#0B5D66", "value": None}, {"color": "#C2410C", "value": v}]  # noqa: E731
green_over = lambda v: [{"color": "#C2410C", "value": None}, {"color": "#0B5D66", "value": v}]  # noqa: E731

kpis = board("bhojango-pilot-kpis", "Pilot KPIs", [
    stat(1, "Orders on their way", f"bhojango_orders_live{S}", 0, 0),
    stat(2, "Orders today", f"bhojango_orders_today{S}", 4, 0),
    stat(3, "Sales today", f"sum(bhojango_gmv_today{S})", 8, 0, decimals=0),
    stat(4, "Median delivery (min)", f"bhojango_median_delivery_minutes{S}", 12, 0, decimals=1, thresholds=red_over(40)),
    stat(5, "On time", f"bhojango_on_time_percent{S}", 16, 0, unit="percent", thresholds=green_over(90)),
    stat(6, "Completed", f"bhojango_completed_percent{S}", 20, 0, unit="percent", thresholds=green_over(95)),
    stat(7, "Refunded", f"bhojango_refund_percent{S}", 0, 4, unit="percent", thresholds=red_over(5)),
    stat(8, "Waiting for a rider", f"bhojango_orders_waiting_for_rider{S}", 4, 4, thresholds=red_over(1)),
    stat(9, "No rider for 5+ min", f"bhojango_orders_waiting_for_rider_5m{S}", 8, 4, thresholds=red_over(1)),
    stat(10, "Late (5+ min)", f"bhojango_orders_late{S}", 12, 4, thresholds=red_over(1)),
    stat(11, "Payment failures (15 min)", f"bhojango_payment_failures_15m{S}", 16, 4, thresholds=red_over(3)),
    stat(12, "KPIs updated", "time() - bhojango_kpi_refreshed_timestamp_seconds", 20, 4, unit="s", thresholds=red_over(120)),
    series(13, "Orders", [(f"bhojango_orders_live{S}", "on their way"), (f"bhojango_orders_waiting_for_rider{S}", "waiting for a rider"),
                          (f"bhojango_orders_late{S}", "late")], 0, 8),
    series(14, "Service", [(f"bhojango_on_time_percent{S}", "on time %"), (f"bhojango_completed_percent{S}", "completed %")], 12, 8, unit="percent"),
    series(15, "Median delivery minutes", [(f"bhojango_median_delivery_minutes{S}", "median")], 0, 16),
    series(16, "Payment failures (last 15 min)", [(f"bhojango_payment_failures_15m{S}", "failed")], 12, 16),
], [city])

health = board("bhojango-service-health", "Service health", [
    series(1, "Requests per second", [('sum by (service) (rate(http_requests_total[5m]))', "{{service}}")], 0, 0),
    series(2, "Errors (5xx) per second", [('sum by (service) (rate(http_requests_total{status="5xx"}[5m]))', "{{service}}")], 12, 0),
    series(3, "p95 response time", [('histogram_quantile(0.95, sum by (service, le) (rate(http_request_duration_seconds_bucket[5m])))', "{{service}}")],
           0, 8, unit="s"),
    series(4, "p95 by endpoint (core-api)", [('topk(8, histogram_quantile(0.95, sum by (handler, le) (rate(http_request_duration_seconds_bucket{service="core-api"}[5m]))))', "{{handler}}")],
           12, 8, unit="s"),
    {"id": 5, "type": "logs", "title": "Errors and alerts in the logs (click a trace id for the trace)", "datasource": LOKI,
     "gridPos": {"x": 0, "y": 16, "w": 24, "h": 10},
     "targets": [{"refId": "A", "datasource": LOKI, "expr": '{service=~".+"} |~ "\\"level\\": ?\\"(error|warning)\\"|alert_"'}],
     "options": {"showTime": True, "wrapLogMessage": True}},
])

OUT.mkdir(exist_ok=True)
for b in (kpis, health):
    (OUT / f"{b['uid']}.json").write_text(json.dumps(b, indent=2) + "\n", encoding="utf-8")
print("wrote", len(list(OUT.glob("*.json"))), "dashboards")

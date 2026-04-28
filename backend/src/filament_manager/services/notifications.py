from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta, timezone
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.orm import Session

from filament_manager.core.security import mask_secret, redact_sensitive
from filament_manager.db.models import (
    NotificationDelivery,
    NotificationRule,
    NotificationTarget,
    PrinterEvent,
    utc_now,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SECONDS = 4
QUIET_CRITICAL_EVENT_TYPES = {"print.failed", "print.cancelled", "hms.error"}


def list_targets(db: Session) -> list[NotificationTarget]:
    return list(db.scalars(select(NotificationTarget).order_by(NotificationTarget.id)).all())


def create_target(db: Session, *, channel: str, name: str, enabled: bool, config: dict[str, Any]) -> NotificationTarget:
    target = NotificationTarget(
        channel=channel,
        name=name.strip(),
        enabled=enabled,
        config=config,
        display_config=redact_notification_config(config),
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def update_target(
    db: Session,
    target: NotificationTarget,
    *,
    channel: str | None = None,
    name: str | None = None,
    enabled: bool | None = None,
    config: dict[str, Any] | None = None,
) -> NotificationTarget:
    if channel is not None:
        target.channel = channel
    if name is not None:
        target.name = name.strip()
    if enabled is not None:
        target.enabled = enabled
    if config is not None:
        target.config = config
        target.display_config = redact_notification_config(config)
    target.updated_at = utc_now()
    db.add(target)
    db.commit()
    db.refresh(target)
    return target


def delete_target(db: Session, target: NotificationTarget) -> None:
    db.delete(target)
    db.commit()


def list_rules(db: Session) -> list[NotificationRule]:
    return list(db.scalars(select(NotificationRule).order_by(NotificationRule.id)).all())


def create_rule(
    db: Session,
    *,
    name: str,
    enabled: bool,
    event_types: list[str],
    printer_ids: list[int],
    severities: list[str],
    quiet_policy: dict[str, Any],
) -> NotificationRule:
    rule = NotificationRule(
        name=name.strip(),
        enabled=enabled,
        event_types=_clean_strings(event_types),
        printer_ids=_clean_ints(printer_ids),
        severities=_clean_strings(severities),
        quiet_policy=quiet_policy,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(
    db: Session,
    rule: NotificationRule,
    *,
    name: str | None = None,
    enabled: bool | None = None,
    event_types: list[str] | None = None,
    printer_ids: list[int] | None = None,
    severities: list[str] | None = None,
    quiet_policy: dict[str, Any] | None = None,
) -> NotificationRule:
    if name is not None:
        rule.name = name.strip()
    if enabled is not None:
        rule.enabled = enabled
    if event_types is not None:
        rule.event_types = _clean_strings(event_types)
    if printer_ids is not None:
        rule.printer_ids = _clean_ints(printer_ids)
    if severities is not None:
        rule.severities = _clean_strings(severities)
    if quiet_policy is not None:
        rule.quiet_policy = quiet_policy
    rule.updated_at = utc_now()
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule: NotificationRule) -> None:
    db.delete(rule)
    db.commit()


def list_deliveries(db: Session, *, limit: int = 100) -> list[NotificationDelivery]:
    return list(
        db.scalars(
            select(NotificationDelivery)
            .order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())
            .limit(limit)
        ).all()
    )


def test_target(db: Session, target: NotificationTarget) -> NotificationDelivery:
    delivery = NotificationDelivery(
        target_id=target.id,
        rule_id=None,
        event_id=None,
        printer_id=None,
        event_type="notification.test",
        status="pending",
    )
    db.add(delivery)
    db.flush()
    _send_and_update_delivery(
        target,
        delivery,
        {
            "event_type": "notification.test",
            "severity": "info",
            "message": "FilamentManager notification test",
            "created_at": utc_now().isoformat(),
        },
    )
    db.commit()
    db.refresh(delivery)
    return delivery


def dispatch_event_notifications(db: Session, event: PrinterEvent) -> list[NotificationDelivery]:
    deliveries: list[NotificationDelivery] = []
    try:
        targets = [target for target in list_targets(db) if target.enabled]
        if not targets:
            return []
        rules = [rule for rule in list_rules(db) if rule.enabled and _rule_matches(rule, event)]
        for rule in rules:
            for target in targets:
                delivery = _delivery_for_rule(db, target=target, rule=rule, event=event)
                deliveries.append(delivery)
    except Exception:
        LOGGER.exception("Notification dispatch failed for printer event id %s", event.id)
    return deliveries


def notification_config_summary(db: Session) -> dict[str, Any]:
    targets = list_targets(db)
    rules = list_rules(db)
    recent = list_deliveries(db, limit=20)
    return {
        "target_count": len(targets),
        "enabled_target_count": sum(1 for target in targets if target.enabled),
        "rule_count": len(rules),
        "enabled_rule_count": sum(1 for rule in rules if rule.enabled),
        "targets": [
            {
                "id": target.id,
                "channel": target.channel,
                "name": target.name,
                "enabled": target.enabled,
                "config": redact_notification_config(target.config),
            }
            for target in targets
        ],
        "recent_delivery_status": [
            {
                "id": row.id,
                "target_id": row.target_id,
                "event_type": row.event_type,
                "status": row.status,
                "error_summary": row.error_summary,
                "created_at": row.created_at,
            }
            for row in recent
        ],
    }


def redact_notification_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    redacted = dict(redact_sensitive(config))  # type: ignore[arg-type]
    for key in ("url", "webhook_url", "endpoint", "topic_url"):
        if key in redacted and redacted[key]:
            redacted[key] = _redact_url(str(redacted[key]))
    for key in ("token", "authorization", "bearer_token", "password"):
        if key in redacted and redacted[key] is not None:
            redacted[key] = mask_secret(str(redacted[key]))
    headers = redacted.get("headers")
    if isinstance(headers, dict):
        for key, value in list(headers.items()):
            if key.lower() in {"authorization", "x-api-key", "x-token"}:
                headers[key] = mask_secret(str(value))
    return redacted


def _delivery_for_rule(
    db: Session,
    *,
    target: NotificationTarget,
    rule: NotificationRule,
    event: PrinterEvent,
) -> NotificationDelivery:
    status, reason = _suppression_status(db, target=target, rule=rule, event=event)
    delivery = NotificationDelivery(
        target_id=target.id,
        rule_id=rule.id,
        event_id=event.id,
        printer_id=event.printer_id,
        event_type=event.event_type,
        status=status,
        error_summary=reason,
    )
    db.add(delivery)
    db.flush()
    if status == "pending":
        _send_and_update_delivery(target, delivery, _event_payload(event))
    return delivery


def _suppression_status(
    db: Session,
    *,
    target: NotificationTarget,
    rule: NotificationRule,
    event: PrinterEvent,
) -> tuple[str, str | None]:
    policy = rule.quiet_policy if isinstance(rule.quiet_policy, dict) else {}
    if _in_suppression_window(db, target=target, event=event, policy=policy):
        return "suppressed", "repeat suppression window"
    if _in_quiet_hours(policy) and not _event_bypasses_quiet_hours(event):
        behavior = str(policy.get("quiet_behavior") or "skip").lower()
        return ("delayed" if behavior == "delay" else "skipped"), "quiet hours"
    return "pending", None


def _send_and_update_delivery(target: NotificationTarget, delivery: NotificationDelivery, payload: dict[str, Any]) -> None:
    try:
        response_status = _send_target(target, payload)
    except Exception as exc:  # noqa: BLE001 - notifications must not break telemetry processing.
        delivery.status = "failed"
        delivery.error_summary = _short_error(exc)
        delivery.sent_at = utc_now()
        return
    delivery.status = "sent"
    delivery.response_status = response_status
    delivery.sent_at = utc_now()


def _send_target(target: NotificationTarget, payload: dict[str, Any]) -> int | None:
    if target.channel == "webhook":
        return _send_webhook(target.config or {}, payload)
    if target.channel == "ntfy":
        return _send_ntfy(target.config or {}, payload)
    raise ValueError(f"Unsupported notification channel: {target.channel}")


def _send_webhook(config: dict[str, Any], payload: dict[str, Any]) -> int:
    url = str(config.get("url") or config.get("webhook_url") or "").strip()
    if not url:
        raise ValueError("Webhook URL is required")
    if url.startswith("mock://"):
        return 200
    headers = {"Content-Type": "application/json", **_string_headers(config.get("headers"))}
    token = config.get("token") or config.get("bearer_token")
    if token and "Authorization" not in headers and "authorization" not in {key.lower(): value for key, value in headers.items()}:
        headers["Authorization"] = f"Bearer {token}"
    return _post(url, headers=headers, body=json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def _send_ntfy(config: dict[str, Any], payload: dict[str, Any]) -> int:
    url = str(config.get("url") or config.get("topic_url") or "").strip()
    if not url:
        server = str(config.get("server") or "https://ntfy.sh").rstrip("/")
        topic = str(config.get("topic") or "").strip("/")
        if topic:
            url = f"{server}/{topic}"
    if not url:
        raise ValueError("ntfy URL or topic is required")
    if url.startswith("mock://"):
        return 200
    headers = {"Title": "FilamentManager", "Tags": _ntfy_tags(payload)}
    token = config.get("token") or config.get("bearer_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = str(payload.get("message") or payload.get("event_type") or "FilamentManager event").encode("utf-8")
    return _post(url, headers=headers, body=body)


def _post(url: str, *, headers: dict[str, str], body: bytes) -> int:
    request = Request(url, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:  # noqa: S310 - user-configured local notification target.
        return int(getattr(response, "status", 200))


def _rule_matches(rule: NotificationRule, event: PrinterEvent) -> bool:
    event_types = set(_clean_strings(rule.event_types or []))
    if event_types and event.event_type not in event_types:
        return False
    printer_ids = set(_clean_ints(rule.printer_ids or []))
    if printer_ids and event.printer_id not in printer_ids:
        return False
    severities = set(_clean_strings(rule.severities or []))
    if severities and event.severity not in severities:
        return False
    return True


def _event_payload(event: PrinterEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "printer_id": event.printer_id,
        "event_type": event.event_type,
        "severity": event.severity,
        "message": event.message,
        "data": redact_sensitive(event.data or {}),
        "created_at": event.created_at.isoformat(),
    }


def _in_suppression_window(
    db: Session,
    *,
    target: NotificationTarget,
    event: PrinterEvent,
    policy: dict[str, Any],
) -> bool:
    minutes = _as_int(policy.get("repeat_suppression_minutes") or policy.get("dedupe_minutes"))
    if not minutes:
        return False
    cutoff = utc_now() - timedelta(minutes=minutes)
    existing = db.scalars(
        select(NotificationDelivery)
        .where(
            NotificationDelivery.target_id == target.id,
            NotificationDelivery.printer_id == event.printer_id,
            NotificationDelivery.event_type == event.event_type,
            NotificationDelivery.status == "sent",
            NotificationDelivery.created_at >= cutoff,
        )
        .limit(1)
    ).first()
    return existing is not None


def _in_quiet_hours(policy: dict[str, Any]) -> bool:
    start = _parse_hhmm(policy.get("quiet_start") or policy.get("start"))
    end = _parse_hhmm(policy.get("quiet_end") or policy.get("end"))
    if start is None or end is None:
        return False
    current = datetime.now(timezone.utc).time()
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def _event_bypasses_quiet_hours(event: PrinterEvent) -> bool:
    if event.event_type in QUIET_CRITICAL_EVENT_TYPES:
        return True
    return event.severity in {"error", "fatal"} and event.event_type.startswith("hms.")


def _parse_hhmm(value: Any) -> time | None:
    if value is None or value == "":
        return None
    parts = str(value).split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def _string_headers(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if item is not None}


def _ntfy_tags(payload: dict[str, Any]) -> str:
    severity = str(payload.get("severity") or "info")
    if severity in {"error", "fatal"}:
        return "warning"
    if severity == "warning":
        return "warning"
    return "information_source"


def _redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return mask_secret(value) or "****"
    sensitive_keys = {"token", "access_token", "key", "secret", "auth", "signature", "sig"}
    query = [
        (key, mask_secret(item) if key.lower() in sensitive_keys else item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    path_parts = [
        mask_secret(part) if len(part) > 24 and any(char.isdigit() for char in part) else part
        for part in parsed.path.split("/")
    ]
    return urlunsplit((parsed.scheme, parsed.netloc, "/".join(path_parts), urlencode(query), parsed.fragment))


def _short_error(exc: Exception) -> str:
    if isinstance(exc, URLError) and exc.reason:
        return str(exc.reason)[:300]
    return str(exc)[:300]


def _clean_strings(values: list[Any]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def _clean_ints(values: list[Any]) -> list[int]:
    cleaned: list[int] = []
    for value in values:
        parsed = _as_int(value)
        if parsed is not None and parsed not in cleaned:
            cleaned.append(parsed)
    return cleaned


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

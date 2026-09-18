"""Alert delivery: console, webhook (HTTP POST) and optional email (SMTP)."""
from __future__ import annotations

import json

from config import (ALERT_EMAIL, ALERT_WEBHOOK, SMTP_HOST, SMTP_PASS,
                    SMTP_PORT, SMTP_USER)


def notify(alert: dict, context: dict | None = None):
    """Deliver one alert. Never raises - delivery failures are logged."""
    sev = str(alert.get('severity', 'info')).upper()
    line = f"[{sev}] {alert.get('kind')}: {alert.get('message')}"
    print(line)

    if ALERT_WEBHOOK:
        _post_webhook(ALERT_WEBHOOK, {"alert": alert, "context": context or {}})
    if ALERT_EMAIL and SMTP_HOST:
        _send_email(ALERT_EMAIL, f"[Farm alert] {alert.get('kind')}",
                    line + "\n\n" + json.dumps(context or {}, indent=2))


def _post_webhook(url, payload):
    try:
        import requests
        requests.post(url, json=payload, timeout=8)
    except Exception as exc:
        print(f"  (webhook delivery failed: {exc})")


def _send_email(to_addr, subject, body):
    try:
        import smtplib
        from email.message import EmailMessage
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_USER or "farm@localhost"
        msg["To"] = to_addr
        msg.set_content(body)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls()
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
    except Exception as exc:
        print(f"  (email delivery failed: {exc})")

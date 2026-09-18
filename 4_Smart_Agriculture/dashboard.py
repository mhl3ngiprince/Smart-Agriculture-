"""Server-rendered HTML dashboard for the Smart Agriculture system.

Design rules (applied to every dashboard in this repo):
  * NO emoji. Icons are inline SVG defined in ``ICONS``.
  * Data comes only from real sources: ``readings`` = device telemetry,
    ``weather_daily`` = observed weather. Modelled values are never shown as
    measurements, and each source is labelled.
  * Charts are drawn from real rows (plain SVG, no CDN/JS dependency).
"""
from __future__ import annotations

import html
import json

import database as db

# ------------------------------------------------------------------ icons ----
# Minimal, dependency-free SVG icons. Add new ones here rather than emoji.
ICONS = {
    "gauge": '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
             'stroke="currentColor" stroke-width="2"><path d="M12 14a2 2 0 1 0 '
             '0-4 2 2 0 0 0 0 4z"/><path d="M12 12l4-4"/><path d="M3 12a9 9 0 '
             '1 1 18 0"/></svg>',
    "droplet": '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
               'stroke="currentColor" stroke-width="2"><path d="M12 3s6 6 6 10a6 '
               '6 0 0 1-12 0c0-4 6-10 6-10z"/></svg>',
    "thermometer": '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
                   'stroke="currentColor" stroke-width="2"><path d="M14 14V5a2 '
                   '2 0 1 0-4 0v9a4 4 0 1 0 4 0z"/></svg>',
    "rain": '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
            'stroke="currentColor" stroke-width="2"><path d="M6 15a4 4 0 0 1 '
            '0-8 5 5 0 0 1 9-2 4 4 0 0 1 3 10"/><path d="M8 18l-1 3M12 18l-1 '
            '3M16 18l-1 3"/></svg>',
    "pump": '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
            'stroke="currentColor" stroke-width="2"><circle cx="9" cy="9" '
            'r="3"/><path d="M12 9h6a2 2 0 0 1 2 2v6M3 20h16"/></svg>',
    "alert": '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
             'stroke="currentColor" stroke-width="2"><path d="M12 3l9 16H3z"/>'
             '<path d="M12 10v4M12 17h.01"/></svg>',
    "device": '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
              'stroke="currentColor" stroke-width="2"><rect x="7" y="3" '
              'width="10" height="18" rx="2"/><path d="M11 18h2"/></svg>',
}


def icon(name: str) -> str:
    return ICONS.get(name, "")


# --------------------------------------------------------------- fragments ---
def _card(title, icon_name, body, span=1):
    return (f'<section class="card" style="grid-column:span {span}">'
            f'<h2>{icon(icon_name)}<span>{html.escape(title)}</span></h2>'
            f'{body}</section>')


def _sparkline(values, color="#3b82f6", height=48, width=240):
    """Plain-SVG sparkline from real numeric values."""
    pts = [v for v in values if v is not None]
    if len(pts) < 2:
        return '<p class="muted">Not enough data to plot.</p>'
    lo, hi = min(pts), max(pts)
    rng = (hi - lo) or 1.0
    step = width / (len(pts) - 1)
    coords = " ".join(
        f"{i * step:.1f},{height - (v - lo) / rng * (height - 6) - 3:.1f}"
        for i, v in enumerate(pts))
    return (f'<svg class="spark" viewBox="0 0 {width} {height}" '
            f'preserveAspectRatio="none">'
            f'<polyline fill="none" stroke="{color}" stroke-width="2" '
            f'points="{coords}"/></svg>')


def _bar_chart(labels, values, color="#3b82f6", height=140):
    if not values:
        return '<p class="muted">No data.</p>'
    hi = max(values) or 1.0
    bars = []
    n = len(values)
    w = 100 / max(n, 1)
    for i, (lab, v) in enumerate(zip(labels, values)):
        h = (v / hi) * 100
        bars.append(
            f'<div class="bar" style="left:{i * w:.3f}%;width:{w:.3f}%" '
            f'title="{html.escape(str(lab))}: {v}">'
            f'<span style="height:{h:.1f}%;background:{color}"></span></div>')
    return (f'<div class="barchart" style="height:{height}px">'
            + "".join(bars) + '</div>')


# ------------------------------------------------------------------- page -----
def _stat(label, value, unit="", icon_name="gauge"):
    return (f'<div class="stat"><div class="stat-ico">{icon(icon_name)}</div>'
            f'<div><div class="stat-val">{html.escape(str(value))}'
            f'<small>{html.escape(unit)}</small></div>'
            f'<div class="stat-lab">{html.escape(label)}</div></div></div>')


def _table(headers, rows):
    if not rows:
        return '<p class="muted">No rows.</p>'
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = ""
    for r in rows:
        body += "<tr>" + "".join(
            f"<td>{html.escape(str(c)) if c is not None else '&mdash;'}</td>"
            for c in r) + "</tr>"
    return f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def render(conn=None) -> str:
    conn = conn or db.get_conn()
    latest = db.latest_reading(conn) or {}
    actuators = db.actuator_states(conn)
    pump = next((a for a in actuators if a["name"] == "pump"), None)
    weather = db.weather_daily(conn, limit=14)
    series = db.readings_timeseries(conn, hours=48)
    alerts = db.recent_alerts(conn, 12)
    summary = db.summary(conn)

    moist_values = [s["soil_moisture"] for s in series]
    temps = [s["temperature"] for s in series]

    cards = [
        _card("Live telemetry", "droplet",
              _stat("Soil moisture", latest.get("soil_moisture", "-"), "%",
                    "droplet")
              + _stat("Air temperature", latest.get("temperature", "-"), "°C",
                      "thermometer")
              + _stat("Humidity", latest.get("humidity", "-"), "%", "gauge")
              + '<p class="src">Source: device telemetry (readings table)</p>'),
        _card("Irrigation", "pump",
              _stat("Pump", (pump or {}).get("state", "unknown"), "", "pump")
              + f'<p class="muted">{html.escape((pump or {}).get("reason", "") or "")}</p>'
              + f'<p class="muted">Irrigation events: {summary["irrigations"]}</p>'),
        _card("Weather - observed", "rain",
              _stat("Rain today", weather[0]["rain_mm"] if weather else "-", "mm",
                    "rain")
              + _stat("Max temp today",
                      weather[0]["temp_max"] if weather else "-", "°C",
                      "thermometer")
              + '<p class="src">Source: Open-Meteo ERA5 observations '
                '(weather_daily table)</p>'),
        _card("Soil moisture - last 48 samples", "gauge",
              _sparkline(moist_values, "#3b82f6")),
        _card("Temperature - last 48 samples", "thermometer",
              _sparkline(temps, "#f59e0b")),
        _card("Rainfall - last 14 observed days", "rain",
              _bar_chart([w["date"][5:] for w in reversed(weather)],
                         [w["rain_mm"] or 0 for w in reversed(weather)],
                         "#3b82f6")),
        _card("Recent alerts", "alert",
              _table(["time", "severity", "kind", "message"],
                     [(a["ts"], a["severity"], a["kind"], a["message"])
                      for a in alerts]), span=2),
        _card("Devices", "device",
              _table(["device", "plot", "crop", "last seen"],
                     [(d["device_id"], d["plot"], d["crop"], d["last_seen"])
                      for d in db.devices(conn)])),
    ]
    return _PAGE.format(cards="".join(cards), summary=html.escape(
        json.dumps(summary)))


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Agriculture - Dashboard</title>
<style>
 :root{{--bg:#0f1115;--panel:#171a21;--line:#242833;--txt:#e8e8e8;
        --muted:#8b93a7;--accent:#3b82f6;--ok:#22c55e;--warn:#f59e0b;
        --crit:#ef4444}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--bg);color:var(--txt);
       font:14px/1.5 system-ui,Segoe UI,Roboto,Arial,sans-serif}}
 header{{display:flex;align-items:center;gap:12px;padding:14px 20px;
         background:var(--panel);border-bottom:1px solid var(--line)}}
 header h1{{font-size:16px;margin:0;font-weight:600}}
 header .sub{{color:var(--muted);font-size:12px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));
        gap:16px;padding:20px}}
 .card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;
        padding:16px}}
 .card h2{{display:flex;align-items:center;gap:8px;margin:0 0 12px;
           font-size:12px;text-transform:uppercase;letter-spacing:.06em;
           color:var(--muted);font-weight:600}}
 .card h2 svg{{color:var(--accent)}}
 .stat{{display:flex;align-items:center;gap:12px;margin:10px 0}}
 .stat-ico{{color:var(--accent)}}
 .stat-val{{font-size:22px;font-weight:700}}
 .stat-val small{{font-size:12px;color:var(--muted);margin-left:4px}}
 .stat-lab{{font-size:12px;color:var(--muted)}}
 .src{{font-size:11px;color:var(--muted);margin:10px 0 0;
       border-top:1px dashed var(--line);padding-top:8px}}
 .muted{{color:var(--muted);font-size:12px}}
 .spark{{width:100%;height:56px;display:block}}
 .barchart{{position:relative;display:flex;align-items:flex-end;
            border-bottom:1px solid var(--line)}}
 .bar{{position:absolute;bottom:0;height:100%;display:flex;
       align-items:flex-end;padding:0 1px}}
 .bar span{{width:100%;border-radius:2px 2px 0 0;min-height:1px;display:block}}
 table{{width:100%;border-collapse:collapse;font-size:13px}}
 th,td{{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line)}}
 th{{color:var(--muted);font-weight:600;font-size:11px;
     text-transform:uppercase;letter-spacing:.05em}}
 footer{{color:var(--muted);font-size:12px;padding:0 20px 24px}}
</style></head>
<body>
<header>
 <h1>Smart Agriculture</h1>
 <span class="sub">Live monitoring &amp; irrigation control</span>
</header>
<div class="grid">{cards}</div>
<footer>DB totals: {summary}</footer>
</body></html>"""

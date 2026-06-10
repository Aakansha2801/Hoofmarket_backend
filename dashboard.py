#!/usr/bin/env python3
"""
HoofMarketIQ — Dashboard Server
A beautiful dark-themed inspection dashboard for reviewing scraped listings.

Usage:
    python dashboard.py

Then open: http://127.0.0.1:8000/
"""

import json
import math
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from collections import defaultdict

# ── Try to import Supabase client ─────────────────────────────
try:
    from db.supabase_client import get_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

HOST = "127.0.0.1"
PORT = 8000

# ── HTML Templates ─────────────────────────────────────────────

BASE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — HoofMarketIQ</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@300;400;500;600&display=swap');

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg:        #0d0f14;
      --bg2:       #13161e;
      --bg3:       #191d27;
      --border:    rgba(255,255,255,0.07);
      --border2:   rgba(255,255,255,0.12);
      --text:      #e8eaf0;
      --text2:     #8a8fa8;
      --text3:     #5a5f75;
      --accent:    #c8a96e;
      --accent2:   #7eb8a0;
      --accent3:   #7b8fcf;
      --danger:    #d06060;
      --success:   #5aab80;
      --warning:   #c8a030;
      --tag-axis:  #2a5a3a;
      --tag-bb:    #3a3060;
      --tag-aou:   #5a3020;
      --tag-other: #303040;
    }}

    body {{
      font-family: 'Sora', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.6;
    }}

    /* ── Sidebar ── */
    .layout {{ display: flex; min-height: 100vh; }}

    .sidebar {{
      width: 220px;
      flex-shrink: 0;
      background: var(--bg2);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      padding: 24px 0;
      position: fixed;
      top: 0; left: 0; bottom: 0;
      z-index: 100;
    }}

    .sidebar-logo {{
      padding: 0 20px 28px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 20px;
    }}

    .sidebar-logo .brand {{
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.15em;
      color: var(--accent);
      text-transform: uppercase;
    }}

    .sidebar-logo .name {{
      font-size: 18px;
      font-weight: 600;
      color: var(--text);
      margin-top: 2px;
    }}

    .nav-section {{
      padding: 0 12px;
      margin-bottom: 8px;
    }}

    .nav-label {{
      font-size: 10px;
      font-weight: 500;
      letter-spacing: 0.12em;
      color: var(--text3);
      text-transform: uppercase;
      padding: 0 8px;
      margin-bottom: 6px;
    }}

    .nav-link {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 9px 10px;
      border-radius: 8px;
      color: var(--text2);
      text-decoration: none;
      font-size: 13.5px;
      font-weight: 400;
      transition: all 0.15s;
      margin-bottom: 2px;
    }}

    .nav-link:hover {{ background: var(--bg3); color: var(--text); }}
    .nav-link.active {{ background: rgba(200,169,110,0.12); color: var(--accent); }}

    .nav-link .icon {{ font-size: 16px; opacity: 0.7; }}

    .sidebar-status {{
      margin-top: auto;
      padding: 16px 20px;
      border-top: 1px solid var(--border);
    }}

    .status-dot {{
      width: 7px; height: 7px;
      border-radius: 50%;
      background: var(--success);
      display: inline-block;
      margin-right: 7px;
      box-shadow: 0 0 6px var(--success);
    }}

    .status-dot.error {{ background: var(--danger); box-shadow: 0 0 6px var(--danger); }}

    .status-text {{ font-size: 12px; color: var(--text2); }}

    /* ── Main content ── */
    .main {{
      margin-left: 220px;
      flex: 1;
      padding: 32px 36px;
      max-width: 1400px;
    }}

    /* ── Page header ── */
    .page-header {{
      margin-bottom: 28px;
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 16px;
    }}

    .page-eyebrow {{
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.12em;
      color: var(--accent);
      text-transform: uppercase;
      margin-bottom: 6px;
    }}

    .page-title {{
      font-size: 26px;
      font-weight: 600;
      color: var(--text);
    }}

    .page-subtitle {{
      font-size: 13px;
      color: var(--text2);
      margin-top: 4px;
    }}

    /* ── KPI Cards ── */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 28px;
    }}

    .kpi-card {{
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px 20px;
    }}

    .kpi-label {{
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.08em;
      color: var(--text3);
      text-transform: uppercase;
      margin-bottom: 8px;
    }}

    .kpi-value {{
      font-size: 28px;
      font-weight: 600;
      color: var(--text);
      font-variant-numeric: tabular-nums;
    }}

    .kpi-meta {{
      font-size: 12px;
      color: var(--text2);
      margin-top: 5px;
    }}

    .kpi-badge {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 100px;
      font-size: 11px;
      font-weight: 500;
    }}

    .kpi-badge.up {{ background: rgba(90,171,128,0.15); color: var(--success); }}
    .kpi-badge.dn {{ background: rgba(208,96,96,0.15); color: var(--danger); }}
    .kpi-badge.nu {{ background: rgba(138,143,168,0.12); color: var(--text2); }}

    /* ── Filters bar ── */
    .filters-bar {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }}

    .filter-label {{
      font-size: 12px;
      color: var(--text3);
      margin-right: 4px;
    }}

    .filter-chip {{
      display: inline-flex;
      align-items: center;
      padding: 5px 14px;
      border-radius: 100px;
      font-size: 12px;
      font-weight: 500;
      text-decoration: none;
      border: 1px solid var(--border2);
      color: var(--text2);
      background: var(--bg2);
      transition: all 0.15s;
    }}

    .filter-chip:hover {{ border-color: var(--accent); color: var(--accent); }}

    .filter-chip.active {{
      background: rgba(200,169,110,0.12);
      border-color: var(--accent);
      color: var(--accent);
    }}

    /* ── Table ── */
    .table-wrap {{
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
    }}

    .table-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
    }}

    .table-title {{
      font-size: 13px;
      font-weight: 500;
      color: var(--text);
    }}

    .table-count {{
      font-size: 12px;
      color: var(--text3);
      font-family: 'DM Mono', monospace;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}

    thead th {{
      padding: 10px 16px;
      text-align: left;
      font-size: 10.5px;
      font-weight: 500;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text3);
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
    }}

    tbody tr {{
      border-bottom: 1px solid var(--border);
      transition: background 0.1s;
    }}

    tbody tr:last-child {{ border-bottom: none; }}
    tbody tr:hover {{ background: var(--bg3); }}

    tbody td {{
      padding: 11px 16px;
      color: var(--text);
      vertical-align: middle;
    }}

    .td-mono {{
      font-family: 'DM Mono', monospace;
      font-size: 12px;
      color: var(--text2);
    }}

    .td-link {{
      color: var(--accent3);
      text-decoration: none;
      font-weight: 500;
    }}

    .td-link:hover {{ text-decoration: underline; }}

    /* ── Species badges ── */
    .species-badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 500;
      font-family: 'DM Mono', monospace;
      letter-spacing: 0.03em;
    }}

    .species-axis    {{ background: var(--tag-axis);  color: #6fcf97; }}
    .species-blackbuck {{ background: var(--tag-bb); color: #9b8bdf; }}
    .species-aoudad  {{ background: var(--tag-aou);  color: #e4875a; }}
    .species-other   {{ background: var(--tag-other); color: var(--text2); }}

    /* ── Status badges ── */
    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 2px 9px;
      border-radius: 100px;
      font-size: 11px;
      font-weight: 500;
    }}

    .status-badge::before {{
      content: '';
      width: 5px; height: 5px;
      border-radius: 50%;
      flex-shrink: 0;
    }}

    .status-active {{ background: rgba(90,171,128,0.12); color: var(--success); }}
    .status-active::before {{ background: var(--success); }}
    .status-closed {{ background: rgba(138,143,168,0.12); color: var(--text2); }}
    .status-closed::before {{ background: var(--text2); }}
    .status-unknown {{ background: rgba(90,95,117,0.15); color: var(--text3); }}
    .status-unknown::before {{ background: var(--text3); }}

    /* ── Tier badges ── */
    .tier-badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .tier-elite      {{ background: rgba(200,160,48,0.2);  color: #e8c050; border: 1px solid rgba(200,160,48,0.3); }}
    .tier-trophy     {{ background: rgba(123,143,207,0.2); color: #9baad8; border: 1px solid rgba(123,143,207,0.3); }}
    .tier-good       {{ background: rgba(90,171,128,0.15); color: var(--success); border: 1px solid rgba(90,171,128,0.25); }}
    .tier-management {{ background: rgba(90,95,117,0.2);   color: var(--text2); border: 1px solid var(--border); }}
    .tier-none       {{ color: var(--text3); font-style: italic; }}

    /* ── Price ── */
    .price-val {{
      font-family: 'DM Mono', monospace;
      font-size: 13px;
      font-weight: 500;
      color: var(--accent);
    }}

    .price-na {{ color: var(--text3); font-style: italic; font-size: 12px; }}

    /* ── Detail page ── */
    .detail-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }}

    .detail-card {{
      background: var(--bg2);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
    }}

    .detail-card-title {{
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.10em;
      color: var(--accent);
      text-transform: uppercase;
      margin-bottom: 14px;
      padding-bottom: 10px;
      border-bottom: 1px solid var(--border);
    }}

    .detail-row {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      padding: 7px 0;
      border-bottom: 1px solid var(--border);
      font-size: 13px;
    }}

    .detail-row:last-child {{ border-bottom: none; }}

    .detail-key {{
      color: var(--text3);
      font-size: 12px;
      flex-shrink: 0;
      padding-top: 1px;
    }}

    .detail-val {{
      color: var(--text);
      text-align: right;
      word-break: break-all;
      font-family: 'DM Mono', monospace;
      font-size: 12px;
    }}

    .photos-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-top: 8px;
    }}

    .photo-thumb {{
      aspect-ratio: 4/3;
      background: var(--bg3);
      border-radius: 6px;
      overflow: hidden;
      border: 1px solid var(--border);
    }}

    .photo-thumb img {{
      width: 100%; height: 100%;
      object-fit: cover;
    }}

    /* ── Back link ── */
    .back-link {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      color: var(--text2);
      text-decoration: none;
      font-size: 13px;
      margin-bottom: 24px;
      transition: color 0.15s;
    }}

    .back-link:hover {{ color: var(--text); }}

    /* ── Empty state ── */
    .empty-state {{
      text-align: center;
      padding: 60px 20px;
      color: var(--text3);
    }}

    .empty-icon {{ font-size: 40px; margin-bottom: 16px; }}
    .empty-title {{ font-size: 18px; font-weight: 500; color: var(--text2); margin-bottom: 8px; }}
    .empty-msg {{ font-size: 13px; }}

    /* ── Error banner ── */
    .error-banner {{
      background: rgba(208,96,96,0.1);
      border: 1px solid rgba(208,96,96,0.25);
      border-radius: 10px;
      padding: 14px 18px;
      margin-bottom: 24px;
      font-size: 13px;
      color: var(--danger);
    }}

    /* ── Pagination ── */
    .pagination {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 20px;
    }}

    .page-btn {{
      padding: 6px 14px;
      border-radius: 6px;
      border: 1px solid var(--border2);
      background: var(--bg2);
      color: var(--text2);
      font-size: 13px;
      text-decoration: none;
      transition: all 0.15s;
    }}

    .page-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
    .page-btn.active {{ background: rgba(200,169,110,0.12); border-color: var(--accent); color: var(--accent); }}

    /* ── Source site chips ── */
    .site-wb {{ color: #82c4a0; background: rgba(50,120,80,0.15); }}
    .site-bt {{ color: #82a8e4; background: rgba(50,80,160,0.15); }}
    .site-ea {{ color: #e0a060; background: rgba(150,90,30,0.15); }}
    .site-oh {{ color: #c080e0; background: rgba(100,50,140,0.15); }}

    .site-chip {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 500;
    }}

    /* ── Review flag ── */
    .review-flag {{
      display: inline-block;
      width: 7px; height: 7px;
      border-radius: 50%;
      background: var(--warning);
      margin-left: 4px;
      vertical-align: middle;
    }}

    /* ── Responsive ── */
    @media (max-width: 900px) {{
      .sidebar {{ display: none; }}
      .main {{ margin-left: 0; padding: 20px; }}
      .detail-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<div class="layout">

  <!-- Sidebar -->
  <nav class="sidebar">
    <div class="sidebar-logo">
      <div class="brand">HoofMarket</div>
      <div class="name">IQ</div>
    </div>
    <div class="nav-section">
      <div class="nav-label">Monitor</div>
      <a href="/" class="nav-link {active_listings}">
        <span class="icon">◈</span> Listings
      </a>
      <a href="/stats" class="nav-link {active_stats}">
        <span class="icon">◉</span> Stats
      </a>
    </div>
    <div class="sidebar-status">
      <span class="status-dot {db_status_class}"></span>
      <span class="status-text">{db_status_text}</span>
    </div>
  </nav>

  <!-- Main -->
  <main class="main">
    {body}
  </main>

</div>
</body>
</html>"""

PAGE_SIZE = 50


# ── Data fetching ──────────────────────────────────────────────

def fetch_listings(site_filter=None, species_filter=None, status_filter=None,
                   tier_filter=None, page=1):
    if not SUPABASE_AVAILABLE:
        return [], 0, "Supabase not available — check db/supabase_client.py"

    try:
        client = get_client()
        q = client.table("listings").select("*", count="exact")

        if site_filter:    q = q.eq("source_site",    site_filter)
        if species_filter: q = q.eq("species",         species_filter)
        if status_filter:  q = q.eq("auction_status",  status_filter)
        if tier_filter:    q = q.eq("tier",             tier_filter)

        offset = (page - 1) * PAGE_SIZE
        q = q.order("scraped_at", desc=True).range(offset, offset + PAGE_SIZE - 1)

        r = q.execute()
        return r.data or [], r.count or 0, None
    except Exception as e:
        return [], 0, str(e)


def fetch_stats():
    if not SUPABASE_AVAILABLE:
        return {}
    try:
        client = get_client()
        r = client.table("listings").select(
            "species,tier,auction_status,source_site,price_current,needs_manual_review"
        ).execute()
        rows = r.data or []
        stats = {
            "total": len(rows),
            "active": sum(1 for x in rows if x.get("auction_status") == "active"),
            "with_tier": sum(1 for x in rows if x.get("tier")),
            "needs_review": sum(1 for x in rows if x.get("needs_manual_review")),
            "by_site": defaultdict(int),
            "by_species": defaultdict(int),
            "by_tier": defaultdict(int),
            "prices": [float(x["price_current"]) for x in rows if x.get("price_current")],
        }
        for x in rows:
            stats["by_site"][x.get("source_site") or "unknown"] += 1
            stats["by_species"][x.get("species") or "unknown"] += 1
            stats["by_tier"][x.get("tier") or "untiered"] += 1
        return stats
    except Exception as e:
        return {"error": str(e)}


def fetch_listing_by_id(uid):
    if not SUPABASE_AVAILABLE:
        return None, "Supabase not available"
    try:
        client = get_client()
        r = client.table("listings").select("*").eq("id", uid).limit(1).execute()
        rows = r.data or []
        if not rows:
            return None, "Not found"
        return rows[0], None
    except Exception as e:
        return None, str(e)


# ── Helpers ────────────────────────────────────────────────────

def fmt_price(val):
    if val is None:
        return '<span class="price-na">—</span>'
    return f'<span class="price-val">${float(val):,.0f}</span>'


def species_badge(s):
    cls = {
        "axis": "species-axis",
        "blackbuck": "species-blackbuck",
        "aoudad": "species-aoudad",
    }.get(s, "species-other")
    return f'<span class="species-badge {cls}">{escape(s or "—")}</span>'


def status_badge(s):
    cls = {
        "active": "status-active",
        "closed": "status-closed",
    }.get(s, "status-unknown")
    return f'<span class="status-badge {cls}">{escape(s or "unknown")}</span>'


def tier_badge(t):
    if not t:
        return '<span class="tier-none">—</span>'
    cls = f"tier-{t}"
    return f'<span class="tier-badge {cls}">{escape(t)}</span>'


def site_chip(s):
    cls = {
        "wildlifebuyer": "site-wb",
        "bucktrader": "site-bt",
        "exoticauctions": "site-ea",
        "onlinehuntingauctions": "site-oh",
    }.get(s, "")
    label = {
        "wildlifebuyer": "WB",
        "bucktrader": "BT",
        "exoticauctions": "EA",
        "onlinehuntingauctions": "OHA",
    }.get(s, escape(s or "?"))
    return f'<span class="site-chip {cls}" title="{escape(s or "")}">{label}</span>'


def render_page(title, body, active="listings", db_ok=True, error=None):
    db_class = "" if db_ok else "error"
    db_text = "Supabase connected" if db_ok else "DB unavailable"
    err_html = ""
    if error:
        err_html = f'<div class="error-banner">⚠ {escape(error)}</div>'
    full_body = err_html + body

    html = BASE_HTML.format(
        title=escape(title),
        active_listings="active" if active == "listings" else "",
        active_stats="active" if active == "stats" else "",
        db_status_class=db_class,
        db_status_text=db_text,
        body=full_body,
    )
    return html.encode("utf-8")


def qs(parsed, **overrides):
    """Build query string preserving existing params, overriding specified ones."""
    params = parse_qs(parsed.query)
    flat = {k: v[0] for k, v in params.items()}
    flat.update(overrides)
    # Remove empty
    flat = {k: v for k, v in flat.items() if v}
    if not flat:
        return ""
    return "?" + "&".join(f"{k}={escape(str(v))}" for k, v in flat.items())


# ── Views ──────────────────────────────────────────────────────

def view_listings(parsed):
    q = parse_qs(parsed.query)
    site_filter    = q.get("site", [""])[0]
    species_filter = q.get("species", [""])[0]
    status_filter  = q.get("status", [""])[0]
    tier_filter    = q.get("tier", [""])[0]
    page           = max(1, int(q.get("page", ["1"])[0]))

    listings, total, error = fetch_listings(
        site_filter or None,
        species_filter or None,
        status_filter or None,
        tier_filter or None,
        page,
    )

    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    db_ok = error is None

    # ── KPI row (quick counts from this page for now) ──
    active_cnt = sum(1 for l in listings if l.get("auction_status") == "active")
    review_cnt = sum(1 for l in listings if l.get("needs_manual_review"))
    tiered_cnt = sum(1 for l in listings if l.get("tier"))
    prices = [float(l["price_current"]) for l in listings if l.get("price_current")]
    avg_price = sum(prices) / len(prices) if prices else 0

    kpi = f"""
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">Total (all pages)</div>
    <div class="kpi-value">{total:,}</div>
    <div class="kpi-meta">Page {page} of {total_pages}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Active (this page)</div>
    <div class="kpi-value">{active_cnt}</div>
    <div class="kpi-meta">of {len(listings)} shown</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Avg Price (this page)</div>
    <div class="kpi-value">${avg_price:,.0f}</div>
    <div class="kpi-meta">{len(prices)} priced</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Need Review</div>
    <div class="kpi-value" style="color: {'var(--warning)' if review_cnt else 'var(--text)'};">{review_cnt}</div>
    <div class="kpi-meta">Flagged this page</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Tiered</div>
    <div class="kpi-value">{tiered_cnt}</div>
    <div class="kpi-meta">of {len(listings)} this page</div>
  </div>
</div>"""

    # ── Filter chips ──
    def chip(label, key, val):
        active_val = {"site": site_filter, "species": species_filter,
                      "status": status_filter, "tier": tier_filter}.get(key, "")
        is_active = active_val == val
        href = "/" + qs(parsed, **{key: "" if is_active else val}, page="1")
        cls = "filter-chip active" if is_active else "filter-chip"
        return f'<a href="{href}" class="{cls}">{escape(label)}</a>'

    filter_html = f"""
<div class="filters-bar">
  <span class="filter-label">Site:</span>
  {chip("Wildlifebuyer","site","wildlifebuyer")}
  {chip("Bucktrader","site","bucktrader")}
  {chip("ExoticAuctions","site","exoticauctions")}
  {chip("OHA","site","onlinehuntingauctions")}
  <span style="color:var(--border2);margin:0 4px">|</span>
  <span class="filter-label">Species:</span>
  {chip("Axis","species","axis")}
  {chip("Blackbuck","species","blackbuck")}
  {chip("Aoudad","species","aoudad")}
  <span style="color:var(--border2);margin:0 4px">|</span>
  <span class="filter-label">Status:</span>
  {chip("Active","status","active")}
  {chip("Closed","status","closed")}
  <span style="color:var(--border2);margin:0 4px">|</span>
  <span class="filter-label">Tier:</span>
  {chip("Elite","tier","elite")}
  {chip("Trophy","tier","trophy")}
  {chip("Good","tier","good")}
  {chip("Mgmt","tier","management")}
</div>"""

    # ── Table rows ──
    if not listings:
        table_body = """<div class="empty-state">
  <div class="empty-icon">◌</div>
  <div class="empty-title">No listings found</div>
  <div class="empty-msg">Try adjusting your filters or run the scraper.</div>
</div>"""
    else:
        rows_html = ""
        for i, row in enumerate(listings, start=(page-1)*PAGE_SIZE + 1):
            uid     = escape(str(row.get("id", "")))
            lid     = escape(str(row.get("listing_id") or "—"))
            title   = escape(str(row.get("title") or "Untitled")[:70])
            scraped = escape(str(row.get("scraped_at") or "")[:16])
            adate   = escape(str(row.get("auction_date") or "")[:10])
            loc     = escape(str(row.get("location_state") or row.get("location_region") or "—"))
            review  = '<span class="review-flag" title="Needs manual review"></span>' if row.get("needs_manual_review") else ""

            rows_html += f"""
<tr>
  <td class="td-mono">{i}</td>
  <td>{site_chip(row.get("source_site"))}</td>
  <td class="td-mono" style="font-size:11px;">{lid}</td>
  <td><a href="/listing?id={uid}" class="td-link">{title}</a>{review}</td>
  <td>{species_badge(row.get("species"))}</td>
  <td>{tier_badge(row.get("tier"))}</td>
  <td>{fmt_price(row.get("price_current"))}</td>
  <td>{status_badge(row.get("auction_status"))}</td>
  <td class="td-mono" style="color:var(--text3);">{loc}</td>
  <td class="td-mono" style="color:var(--text3);">{adate or scraped}</td>
  <td><a href="{escape(str(row.get('source_url','#')))}" target="_blank" style="color:var(--text3);font-size:12px;" title="Open source">↗</a></td>
</tr>"""

        table_body = f"""
<table>
  <thead>
    <tr>
      <th>#</th><th>Site</th><th>Listing ID</th><th>Title</th>
      <th>Species</th><th>Tier</th><th>Price</th><th>Status</th>
      <th>Location</th><th>Date</th><th></th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>"""

    # Pagination
    pag = '<div class="pagination">'
    if page > 1:
        pag += f'<a href="/{qs(parsed, page=str(page-1))}" class="page-btn">← Prev</a>'
    for p in range(max(1, page-2), min(total_pages+1, page+3)):
        cls = "page-btn active" if p == page else "page-btn"
        pag += f'<a href="/{qs(parsed, page=str(p))}" class="{cls}">{p}</a>'
    if page < total_pages:
        pag += f'<a href="/{qs(parsed, page=str(page+1))}" class="page-btn">Next →</a>'
    pag += "</div>"

    body = f"""
<div class="page-header">
  <div>
    <div class="page-eyebrow">Texas Market Intelligence</div>
    <div class="page-title">Listings Inspector</div>
    <div class="page-subtitle">Review scraped hoofstock listings — verify data quality, tiers, and extraction accuracy.</div>
  </div>
</div>
{kpi}
{filter_html}
<div class="table-wrap">
  <div class="table-header">
    <span class="table-title">All Listings</span>
    <span class="table-count">{total:,} total · page {page}/{total_pages}</span>
  </div>
  {table_body}
  {pag}
</div>"""

    return render_page("Listings", body, active="listings", db_ok=db_ok, error=error)


def view_listing_detail(parsed):
    q = parse_qs(parsed.query)
    uid = q.get("id", [""])[0]
    if not uid:
        return render_page("Error", "<p>Missing id</p>", db_ok=SUPABASE_AVAILABLE)

    row, error = fetch_listing_by_id(uid)
    if error and not row:
        return render_page("Not Found", f"<p>{escape(error)}</p>", db_ok=SUPABASE_AVAILABLE)

    title = row.get("title") or "Untitled"

    # Photo grid
    photos_html = ""
    photo_urls = row.get("photo_urls")
    if photo_urls:
        if isinstance(photo_urls, str):
            try: photo_urls = json.loads(photo_urls)
            except: photo_urls = [photo_urls]
        thumbs = ""
        for url in (photo_urls or [])[:6]:
            thumbs += f'<div class="photo-thumb"><img src="{escape(str(url))}" loading="lazy" alt="listing photo"></div>'
        if thumbs:
            photos_html = f'<div class="photos-grid">{thumbs}</div>'

    def detail_section(section_title, fields):
        rows = ""
        for k in fields:
            v = row.get(k)
            if v is None:
                display = '<span style="color:var(--text3);font-style:italic;">null</span>'
            elif isinstance(v, (dict, list)):
                inner = escape(json.dumps(v, indent=2, ensure_ascii=False))
                display = f'<pre style="font-family:\'DM Mono\',monospace;font-size:11px;color:var(--text2);white-space:pre-wrap;word-break:break-all;margin:0;">{inner}</pre>'
            elif isinstance(v, bool):
                color = "var(--success)" if v else "var(--danger)"
                display = f'<span style="color:{color};font-weight:500;">{"true" if v else "false"}</span>'
            else:
                display = f'<span style="color:var(--text);">{escape(str(v))}</span>'
            rows += f'<div class="detail-row"><span class="detail-key">{escape(k)}</span><span class="detail-val">{display}</span></div>'
        return f"""
<div class="detail-card">
  <div class="detail-card-title">{escape(section_title)}</div>
  {rows}
</div>"""

    sections = [
        ("Identity", ["id", "listing_id", "source_site", "source_url", "scraped_at"]),
        ("Animal", ["species", "sex", "age_class", "bred_status", "color_phase", "quantity"]),
        ("Pricing", ["price_current", "price_final", "price_start", "easy_bid_price", "bid_count"]),
        ("Auction", ["auction_status", "auction_date"]),
        ("Location", ["location_raw", "location_city", "location_county", "location_region", "location_state"]),
        ("Tier & Quality", ["tier", "tier_confidence", "quality_score", "extraction_notes", "needs_manual_review", "is_active"]),
        ("Measurements", ["primary_measurement_inches", "secondary_measurements"]),
    ]

    grid_html = '<div class="detail-grid">'
    for sec_title, fields in sections:
        grid_html += detail_section(sec_title, fields)
    grid_html += "</div>"

    if photos_html:
        grid_html += f"""
<div class="detail-card" style="margin-top:20px;">
  <div class="detail-card-title">Photos ({len(photo_urls or [])})</div>
  {photos_html}
</div>"""

    # Raw description
    desc_raw = row.get("description_raw") or ""
    if desc_raw:
        grid_html += f"""
<div class="detail-card" style="margin-top:20px;">
  <div class="detail-card-title">Raw Description</div>
  <p style="font-size:13px;color:var(--text2);line-height:1.7;white-space:pre-wrap;">{escape(str(desc_raw)[:3000])}</p>
</div>"""

    body = f"""
<a href="/" class="back-link">← Back to listings</a>
<div class="page-header">
  <div>
    <div class="page-eyebrow">{site_chip(row.get("source_site"))} &nbsp; {species_badge(row.get("species"))}</div>
    <div class="page-title" style="margin-top:8px;">{escape(title[:80])}</div>
    <div class="page-subtitle" style="margin-top:6px;">
      {tier_badge(row.get("tier"))} &nbsp; {status_badge(row.get("auction_status"))} &nbsp;
      {fmt_price(row.get("price_current"))} &nbsp;
      <span style="color:var(--text3);font-size:12px;">ID: {escape(str(row.get('listing_id','—')))}</span>
    </div>
  </div>
  <a href="{escape(str(row.get('source_url','#')))}" target="_blank"
     style="display:inline-flex;align-items:center;gap:6px;padding:10px 18px;border-radius:8px;border:1px solid var(--border2);color:var(--text2);text-decoration:none;font-size:13px;transition:all 0.15s;">
    View Source ↗
  </a>
</div>
{grid_html}"""

    return render_page(title, body, active="listings", db_ok=True, error=error)


def view_stats(parsed):
    stats = fetch_stats()
    error = stats.get("error")
    db_ok = not bool(error)

    if error:
        body = f"""
<div class="page-header">
  <div>
    <div class="page-eyebrow">Database</div>
    <div class="page-title">Stats Overview</div>
  </div>
</div>"""
        return render_page("Stats", body, active="stats", db_ok=False, error=error)

    # Prices
    prices = stats.get("prices", [])
    avg_p = sum(prices)/len(prices) if prices else 0
    med_p = sorted(prices)[len(prices)//2] if prices else 0
    min_p = min(prices) if prices else 0
    max_p = max(prices) if prices else 0

    def kpi_card(label, value, meta=""):
        return f"""<div class="kpi-card">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  {"<div class='kpi-meta'>" + meta + "</div>" if meta else ""}
</div>"""

    kpi_html = f"""<div class="kpi-grid">
  {kpi_card("Total Listings", f"{stats.get('total', 0):,}")}
  {kpi_card("Active", f"{stats.get('active', 0):,}")}
  {kpi_card("Tiered", f"{stats.get('with_tier', 0):,}", f"{stats.get('with_tier',0)/max(stats.get('total',1),1)*100:.0f}% of total")}
  {kpi_card("Need Review", f"{stats.get('needs_review', 0):,}")}
  {kpi_card("Avg Price", f"${avg_p:,.0f}")}
  {kpi_card("Median Price", f"${med_p:,.0f}")}
  {kpi_card("Min / Max", f"${min_p:,.0f} / ${max_p:,.0f}")}
</div>"""

    def breakdown_table(title_str, data_dict):
        rows = ""
        total_count = sum(data_dict.values())
        for k, v in sorted(data_dict.items(), key=lambda x: -x[1]):
            pct = v / total_count * 100 if total_count else 0
            rows += f"""<tr>
  <td style="color:var(--text2);font-size:13px;">{escape(str(k))}</td>
  <td class="td-mono">{v:,}</td>
  <td>
    <div style="background:var(--bg3);border-radius:4px;height:6px;width:120px;">
      <div style="background:var(--accent);border-radius:4px;height:6px;width:{pct:.0f}%;"></div>
    </div>
  </td>
  <td class="td-mono" style="color:var(--text3);">{pct:.1f}%</td>
</tr>"""
        return f"""
<div class="table-wrap" style="margin-bottom:20px;">
  <div class="table-header"><span class="table-title">{escape(title_str)}</span></div>
  <table>
    <thead><tr><th>Name</th><th>Count</th><th>Distribution</th><th>%</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""

    body = f"""
<div class="page-header">
  <div>
    <div class="page-eyebrow">Database Overview</div>
    <div class="page-title">Stats</div>
    <div class="page-subtitle">Aggregate breakdown of all scraped listings.</div>
  </div>
</div>
{kpi_html}
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;margin-top:8px;">
  {breakdown_table("By Source Site", dict(stats.get("by_site", {})))}
  {breakdown_table("By Species", dict(stats.get("by_species", {})))}
  {breakdown_table("By Tier", dict(stats.get("by_tier", {})))}
</div>"""

    return render_page("Stats", body, active="stats", db_ok=db_ok, error=error)


# ── HTTP Handler ───────────────────────────────────────────────

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            html = view_listings(parsed)
        elif parsed.path == "/listing":
            html = view_listing_detail(parsed)
        elif parsed.path == "/stats":
            html = view_stats(parsed)
        else:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} — {fmt % args}")


def run():
    server = HTTPServer((HOST, PORT), DashboardHandler)
    print(f"\n  🦌 HoofMarketIQ Dashboard")
    print(f"  ─────────────────────────")
    print(f"  http://{HOST}:{PORT}/")
    print(f"  http://{HOST}:{PORT}/stats")
    print(f"\n  Supabase: {'✅ client available' if SUPABASE_AVAILABLE else '❌ not available — check db/supabase_client.py'}")
    print(f"\n  Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopping dashboard.")
        server.server_close()


if __name__ == "__main__":
    run()
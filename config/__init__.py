# ============================================================
# HoofMarketIQ — config/__init__.py
# Single import point: `from config import *`
# ============================================================

from config.base    import *      # Supabase, rate limits, TX regions
from config.species import *      # Species tiers & keywords

# Registry of all site configs — add new sites here ONLY
from config.sites import wildlifebuyer, bucktrader

SITE_REGISTRY = {
    "wildlifebuyer": wildlifebuyer,
    "bucktrader":    bucktrader,
    # "exoticauctions": exoticauctions,   ← uncomment when ready
}

# Only enabled sites
ACTIVE_SITES = {
    site_id: mod
    for site_id, mod in SITE_REGISTRY.items()
    if getattr(mod, "ENABLED", False)
}
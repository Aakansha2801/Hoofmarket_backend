# ============================================================
# HoofMarketIQ — config/__init__.py
# Single import point: `from config import *`
# ============================================================

from config.base    import *      # Rate limits, TX regions
from config.species import *      # Species tiers & keywords

# Registry of all site configs — add new sites here ONLY
from config.sites import wildlifebuyer, bucktrader, onlinehuntingauctions

SITE_REGISTRY = {
    "wildlifebuyer": wildlifebuyer,
    "bucktrader":    bucktrader,
    "onlinehuntingauctions": onlinehuntingauctions,
    # "exoticauctions": exoticauctions,   ← uncomment when ready
}

# Only enabled sites
ACTIVE_SITES = {
    site_id: mod
    for site_id, mod in SITE_REGISTRY.items()
    if getattr(mod, "ENABLED", False)
}
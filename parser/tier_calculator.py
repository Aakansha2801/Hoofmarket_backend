# ============================================================
# HoofMarketIQ — parser/tier_calculator.py
# Applies PRD tier rules per species based on primary measurement
# ============================================================

from config.species import SPECIAL_SPECIES_CONFIG


def calculate_tier(species: str, primary_measurement_inches: float | None) -> str | None:
    """
    Return tier string for a special species listing.
    Returns None if species is not special or measurement is missing.

    Tiers per PRD:
      Axis:      management <27 | good 27-30 | trophy 30-34 | elite 34+
      Blackbuck: management <18 | good 18-20 | trophy 20-23 | elite 23+
      Aoudad:    management <30 | good 30-35 | trophy 35-40 | elite 40+
    """
    if species not in SPECIAL_SPECIES_CONFIG or primary_measurement_inches is None:
        return None

    tiers = SPECIAL_SPECIES_CONFIG[species]["tiers"]
    for tier_name, (low, high) in tiers.items():
        if low <= primary_measurement_inches < high:
            return tier_name

    return None


def apply_tier(listing: dict) -> dict:
    """Enrich a listing dict with a 'tier' field. Returns the same dict."""
    listing["tier"] = calculate_tier(
        listing.get("species"),
        listing.get("primary_measurement_inches"),
    )
    return listing

# ============================================================
# HoofMarketIQ — db/supabase_client.py
# ============================================================

from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

_client: Client | None = None


def get_client() -> Client:
    """Return a singleton Supabase client using the service role key."""
    global _client
    if _client is None:
        if not SUPABASE_URL:
            raise ValueError("SUPABASE_URL is not set in config.py")
        if not SUPABASE_SERVICE_KEY:
            raise ValueError("SUPABASE_SERVICE_KEY is not set in config.py")
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def test_connection() -> bool:
    """Quick sanity check — returns True if connection works."""
    try:
        client = get_client()
        result = client.table("listings").select("id").limit(1).execute()
        print("✅ Supabase connection OK")
        print(f"   URL: {SUPABASE_URL}")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False


if __name__ == "__main__":
    test_connection()
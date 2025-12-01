"""
Dream Meridian - Geocode Layer
Extracts place references from queries and resolves to coordinates.
Uses the currently loaded location from spatial_tools.
"""

import duckdb
import re
from statistics import mean
from pathlib import Path

# ============================================================================
# Global State
# ============================================================================
con = None
current_location = None

# ============================================================================
# Location Loading
# ============================================================================

def load_location(slug: str):
    """Load database for a location. Call when user switches cities."""
    global con, current_location
    
    if current_location == slug and con is not None:
        return
    
    db_path = Path("data") / slug / f"{slug}.duckdb"
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    if con is not None:
        con.close()
    
    con = duckdb.connect(str(db_path), read_only=True)
    current_location = slug

# ============================================================================
# Geocoding Functions
# ============================================================================

def get_place_centroid(place_name: str, min_matches: int = 3) -> dict | None:
    """Get centroid coordinates for a place name from OSM features."""
    if con is None:
        return None
    
    results = con.execute("""
        SELECT lat, lon, name FROM osm_features
        WHERE name ILIKE ? LIMIT 50
    """, [f"%{place_name}%"]).fetchall()
    
    if len(results) < min_matches:
        return None
    
    lats = [r[0] for r in results]
    lons = [r[1] for r in results]
    
    return {
        "place": place_name,
        "lat": mean(lats),
        "lon": mean(lons),
        "matches": len(results)
    }

def extract_candidates(query: str) -> list[str]:
    """Extract potential place name candidates from query."""
    # Find capitalized words (likely place names)
    words = re.findall(r'\b[A-Z][a-z]{2,}\b', query)
    
    # Filter out common query words
    stopwords = {
        'Find', 'Show', 'How', 'What', 'Where', 'Many', 'List', 'Count',
        'Near', 'From', 'Within', 'Walking', 'Route', 'Area', 'Distance',
        'Nearest', 'Closest', 'Around', 'Between', 'Minutes', 'Kilometers'
    }
    
    return [w for w in words if w not in stopwords]

def geocode_query(query: str) -> tuple[str, dict]:
    """
    Process a query to resolve place names to coordinates.
    
    Returns:
        tuple: (modified_query, geocode_info)
        - modified_query: Query with place names replaced by coordinates
        - geocode_info: Dict of resolved places with their coordinates
    """
    candidates = extract_candidates(query)
    geocode_info = {}
    modified = query
    
    for candidate in candidates:
        result = get_place_centroid(candidate)
        if result:
            geocode_info[candidate] = result
            # Replace place name with coordinates in query
            pattern = re.compile(re.escape(candidate), re.IGNORECASE)
            modified = pattern.sub(
                f"(lat {result['lat']:.6f}, lon {result['lon']:.6f})",
                modified
            )
    
    return modified, geocode_info
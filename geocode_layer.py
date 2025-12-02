"""
./geocode_layer.py
Dream Meridian - Geocode Layer
Matches known place names from OSM (neighborhoods, suburbs, localities)
against user queries and resolves to coordinates.
"""

import duckdb
import re
from pathlib import Path

# ============================================================================
# Global State
# ============================================================================
con = None
current_location = None
known_places = {}  # name_lower -> {name, lat, lon, place_type}

# ============================================================================
# Location Loading
# ============================================================================

def load_location(slug: str):
    """Load database and place names for a location."""
    global con, current_location, known_places
    
    if current_location == slug and con is not None:
        return
    
    db_path = Path("data") / slug / f"{slug}.duckdb"
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    if con is not None:
        con.close()
    
    con = duckdb.connect(str(db_path), read_only=True)
    current_location = slug
    
    # Load known places into memory for fast matching
    _load_known_places()


def _load_known_places():
    """Load place names from database into memory."""
    global known_places
    known_places = {}
    
    if con is None:
        return
    
    # Check if places table exists
    tables = con.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    
    if 'places' not in table_names:
        print("  ⚠️ No places table found - geocoding will use POI fallback")
        return
    
    results = con.execute("""
        SELECT name, name_lower, lat, lon, place_type 
        FROM places
    """).fetchall()
    
    for name, name_lower, lat, lon, place_type in results:
        known_places[name_lower] = {
            'name': name,
            'lat': lat,
            'lon': lon,
            'place_type': place_type
        }
    
    print(f"  ✓ Loaded {len(known_places):,} place names for geocoding")


# ============================================================================
# Geocoding Functions
# ============================================================================

def find_place_in_query(query: str) -> list[tuple[str, dict]]:
    """
    Find known place names in a query.
    Returns list of (matched_text, place_info) tuples.
    Matches longest places first to handle overlapping names.
    """
    query_lower = query.lower()
    matches = []
    used_spans = []  # Track which parts of query are already matched
    
    # Sort places by name length (longest first) for greedy matching
    sorted_places = sorted(known_places.items(), key=lambda x: -len(x[0]))
    
    for name_lower, info in sorted_places:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(name_lower) + r'\b'
        for match in re.finditer(pattern, query_lower):
            start, end = match.span()
            
            # Check if this span overlaps with an existing match
            overlaps = False
            for used_start, used_end in used_spans:
                if not (end <= used_start or start >= used_end):
                    overlaps = True
                    break
            
            if not overlaps:
                # Get the original case from the query
                original_text = query[start:end]
                matches.append((original_text, info))
                used_spans.append((start, end))
    
    return matches


def get_place_centroid_fallback(place_name: str) -> dict | None:
    """
    Fallback: search POI names if place not in known places.
    Used for landmarks, specific buildings, etc.
    """
    if con is None:
        return None
    
    results = con.execute("""
        SELECT lat, lon, name FROM osm_features
        WHERE name ILIKE ? 
        LIMIT 20
    """, [f"%{place_name}%"]).fetchall()
    
    if len(results) < 1:
        return None
    
    # Return centroid of matches
    lats = [r[0] for r in results]
    lons = [r[1] for r in results]
    
    return {
        "name": place_name,
        "lat": sum(lats) / len(lats),
        "lon": sum(lons) / len(lons),
        "place_type": "poi",
        "matches": len(results)
    }


def geocode_query(query: str) -> tuple[str, dict]:
    """
    Process a query to resolve place names to coordinates.
    Only matches against known places from OSM (neighborhoods, suburbs, etc.)
    
    Returns:
        tuple: (modified_query, geocode_info)
        - modified_query: Query with place names replaced by coordinates
        - geocode_info: Dict of resolved places with their coordinates
    """
    geocode_info = {}
    modified = query
    
    matches = find_place_in_query(query)
    
    for original_text, info in matches:
        geocode_info[info['name']] = {
            'lat': info['lat'],
            'lon': info['lon'],
            'place_type': info['place_type']
        }
        # Replace in query (case-insensitive for Latin script, exact for others)
        pattern = re.compile(re.escape(original_text), re.IGNORECASE)
        modified = pattern.sub(
            f"(lat {info['lat']:.6f}, lon {info['lon']:.6f})",
            modified,
            count=1  # Only replace first occurrence
        )
    
    return modified, geocode_info


def list_known_places() -> list[str]:
    """Return list of known place names (for debugging/display)."""
    return sorted(known_places.keys())
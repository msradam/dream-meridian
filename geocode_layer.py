"""
./geocode_layer.py
Dream Meridian - Geocode Layer
Extracts place references from queries and resolves to coordinates.
Handles multi-word place names like "Old San Juan" and "Rio Piedras".
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
known_places = set()  # Cache of place names from database

# ============================================================================
# Location Loading
# ============================================================================

def load_location(slug: str):
    """Load database for a location. Call when user switches cities."""
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
    
    # Build cache of known place names for faster matching
    _build_place_cache()

def _build_place_cache():
    """Build set of known place names from database for matching."""
    global known_places
    known_places = set()
    
    if con is None:
        return
    
    # Get unique place-like names (neighborhoods, landmarks, etc.)
    # Look for names that appear multiple times (likely neighborhoods)
    results = con.execute("""
        SELECT DISTINCT name 
        FROM osm_features 
        WHERE name IS NOT NULL 
          AND LENGTH(name) > 2
          AND LENGTH(name) < 50
    """).fetchall()
    
    for (name,) in results:
        if name:
            # Store both original and normalized versions
            known_places.add(name.lower())

# ============================================================================
# Geocoding Functions
# ============================================================================

def get_place_centroid(place_name: str, min_matches: int = 1) -> dict | None:
    """Get centroid coordinates for a place name from OSM features."""
    if con is None:
        return None
    
    # Try exact match first, then fuzzy
    results = con.execute("""
        SELECT lat, lon, name FROM osm_features
        WHERE name ILIKE ? 
        LIMIT 50
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
    """
    Extract potential place name candidates from query.
    Handles multi-word place names like "Old San Juan".
    """
    # Words to ignore (common query words, not places)
    stopwords = {
        'find', 'show', 'how', 'what', 'where', 'many', 'list', 'count',
        'near', 'from', 'within', 'walking', 'route', 'area', 'distance',
        'nearest', 'closest', 'around', 'between', 'minutes', 'kilometers',
        'team', 'found', 'injured', 'person', 'need', 'get', 'them',
        'hospital', 'clinic', 'pharmacy', 'shelter', 'school', 'police',
        'fast', 'help', 'emergency', 'medical', 'water', 'food',
        'distributing', 'supplies', 'walkable', 'checking', 'capacity',
        'before', 'storm', 'hits', 'comms', 'down', 'station',
        'resupply', 'first', 'aid', 'kits', 'any', 'planning',
        'evacuation', 'routes', 'convention', 'center', 'facilities',
        'community', 'reporting', 'issues', 'resources', 'close',
        'looking', 'schools', 'use', 'shelters', 'roads', 'flooded',
        'can', 'someone', 'walk', 'the', 'and', 'for', 'with'
    }
    
    # Find sequences of capitalized words (potential multi-word place names)
    # Pattern: one or more capitalized words in sequence
    pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
    sequences = re.findall(pattern, query)
    
    candidates = []
    used_words = set()
    
    # Process longest sequences first (greedy matching)
    sequences.sort(key=lambda x: -len(x.split()))
    
    for seq in sequences:
        words = seq.split()
        
        # Skip if any word already used or is a stopword
        if any(w.lower() in used_words or w.lower() in stopwords for w in words):
            continue
        
        # For multi-word sequences, keep as-is
        if len(words) > 1:
            candidates.append(seq)
            used_words.update(w.lower() for w in words)
        else:
            # Single word - only keep if not a stopword
            word = words[0]
            if word.lower() not in stopwords:
                candidates.append(word)
                used_words.add(word.lower())
    
    return candidates

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
            # Use word boundaries to avoid partial replacements
            pattern = re.compile(re.escape(candidate), re.IGNORECASE)
            modified = pattern.sub(
                f"(lat {result['lat']:.6f}, lon {result['lon']:.6f})",
                modified
            )
    
    return modified, geocode_info
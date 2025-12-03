#!/usr/bin/env python3
"""
./build_location.py
Dream Meridian - Location Builder
Downloads street network and OSM features for any location.

Usage:
    python build_location.py "Dhaka, Bangladesh" dhaka
    python build_location.py "Mandalay, Myanmar" mandalay

    # Optional: download offline tiles (can be slow for large areas)
    python build_location.py "Dhaka, Bangladesh" dhaka --tiles

Output:
    data/{slug}/           - spatial data
    static/tiles/{slug}/   - map tiles (only if --tiles flag used)
"""

import osmnx as ox
import networkit as nk
import duckdb
import pandas as pd
import json
import time
import sys
import math
import requests
import warnings
from pathlib import Path

# Suppress geometry warnings
warnings.filterwarnings("ignore", message=".*Geometry is in a geographic CRS.*")
warnings.filterwarnings("ignore", message=".*Overpass max query area.*")

# ============================================================================
# CONFIGURATION
# ============================================================================

TILE_ZOOM_LEVELS = range(11, 17)
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_RATE_LIMIT = 0.1

# Place names (neighborhoods, suburbs, etc.) for geocoding
PLACE_TAGS = {
    "place": [
        "neighbourhood",
        "neighborhood",
        "suburb",
        "quarter",
        "locality",
        "hamlet",
        "village",
        "town",
        "city",
        "borough",
        "district",
    ],
}

# Humanitarian-relevant OSM tags - ALL IN ONE QUERY
OSM_TAGS = {
    "amenity": [
        # Healthcare
        "hospital",
        "clinic",
        "doctors",
        "pharmacy",
        "dentist",
        "nursing_home",
        "veterinary",  # Important for livestock in rural areas
        # Emergency Services
        "police",
        "fire_station",
        "shelter",
        "emergency_service",
        # Education (often evacuation centers)
        "school",
        "kindergarten",
        "college",
        "university",
        # Community (emergency gathering points)
        "place_of_worship",
        "community_centre",
        "social_facility",
        "refugee_site",
        # Government/Admin
        "townhall",
        "courthouse",
        "embassy",
        "public_building",
        # Financial (cash access during emergencies)
        "bank",
        "atm",
        "money_transfer",
        "mobile_money_agent",
        # Food/Water
        "marketplace",
        "food_court",
        "drinking_water",
        "water_point",
        "toilets",
        # Transport hubs
        "bus_station",
        "ferry_terminal",
        "fuel",
        "parking",
        # Communication
        "post_office",
        "telephone",
        "internet_cafe",
    ],
    "healthcare": True,  # All healthcare facilities
    "emergency": True,  # Fire hydrants, assembly points, sirens
    "shop": [
        # Food
        "supermarket",
        "convenience",
        "grocery",
        "general",
        "food",
        "bakery",
        "butcher",
        "greengrocer",
        "water",
        # Medical
        "pharmacy",
        "chemist",
        "medical_supply",
        # Hardware/Tools
        "hardware",
        "doityourself",
        "electronics",
        # Communication
        "mobile_phone",
    ],
    "building": [
        "hospital",
        "school",
        "university",
        "college",
        "government",
        "civic",
        "public",
        "mosque",
        "temple",
        "church",
        "religious",
        "cathedral",
        "fire_station",
        "police",
        "warehouse",  # For aid storage
    ],
    "office": [
        "government",
        "ngo",
        "diplomatic",
        "humanitarian",
        "un",
        "international_organization",
        "telecommunication",
    ],
    "man_made": [
        "water_tower",
        "water_well",
        "water_works",
        "pumping_station",
        "storage_tank",
        "reservoir_covered",
        "communications_tower",
        "tower",
    ],
    "power": [
        "plant",
        "substation",
        "generator",
    ],
    "aeroway": [
        "aerodrome",
        "helipad",
        "heliport",  # Emergency evacuation
    ],
    "railway": [
        "station",
        "halt",
    ],
    "public_transport": [
        "station",
        "stop_position",
        "platform",
    ],
    "natural": [
        "spring",
        "water",  # Natural water sources
    ],
    "landuse": [
        "cemetery",  # Important for cultural/religious reasons
        "military",  # Often involved in disaster response
    ],
}

# ============================================================================
# TILE FUNCTIONS
# ============================================================================


def get_graph_bounds(G_nx):
    """Extract bounding box from NetworkX graph."""
    lats = [data["y"] for _, data in G_nx.nodes(data=True) if "y" in data]
    lons = [data["x"] for _, data in G_nx.nodes(data=True) if "x" in data]
    padding = 0.005
    return {
        "north": max(lats) + padding,
        "south": min(lats) - padding,
        "east": max(lons) + padding,
        "west": min(lons) - padding,
    }


def get_graph_center(G_nx):
    """Get center point of graph."""
    lats = [data["y"] for _, data in G_nx.nodes(data=True) if "y" in data]
    lons = [data["x"] for _, data in G_nx.nodes(data=True) if "x" in data]
    return {"lat": (max(lats) + min(lats)) / 2, "lon": (max(lons) + min(lons)) / 2}


def lat_lon_to_tile(lat, lon, zoom):
    """Convert lat/lon to tile coordinates."""
    lat_rad = math.radians(lat)
    n = 2**zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(lat_rad)) / math.pi) / 2 * n)
    return x, y


def get_tile_range(bounds, zoom):
    """Get all tile coordinates within bounds for a zoom level."""
    x_min, y_max = lat_lon_to_tile(bounds["south"], bounds["west"], zoom)
    x_max, y_min = lat_lon_to_tile(bounds["north"], bounds["east"], zoom)
    tiles = []
    for x in range(x_min, x_max + 1):
        for y in range(y_min, y_max + 1):
            tiles.append((zoom, x, y))
    return tiles


def download_tiles(bounds, slug, zooms=TILE_ZOOM_LEVELS):
    """Download tiles to static/tiles/{slug}/ for Streamlit serving."""
    print("\n" + "=" * 70)
    print("DOWNLOADING MAP TILES")
    print("=" * 70)

    # Output to static folder for Streamlit
    tile_dir = Path("static") / "tiles" / slug
    tile_dir.mkdir(parents=True, exist_ok=True)

    all_tiles = []
    for z in zooms:
        all_tiles.extend(get_tile_range(bounds, z))

    print(f"\nBounds: N={bounds['north']:.4f} S={bounds['south']:.4f}")
    print(f"        E={bounds['east']:.4f} W={bounds['west']:.4f}")
    print(f"Zoom levels: {min(zooms)}-{max(zooms)}")
    print(f"Total tiles: {len(all_tiles)}")
    print(f"Output: {tile_dir}/")

    headers = {"User-Agent": "DreamMeridian/1.0 (Humanitarian AI Project)"}
    downloaded = skipped = failed = 0
    start_time = time.time()

    for i, (z, x, y) in enumerate(all_tiles):
        tile_path = tile_dir / f"{z}/{x}/{y}.png"

        if tile_path.exists():
            skipped += 1
            continue

        tile_path.parent.mkdir(parents=True, exist_ok=True)

        url = TILE_URL.format(z=z, x=x, y=y)
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                tile_path.write_bytes(resp.content)
                downloaded += 1
            else:
                failed += 1
        except:
            failed += 1

        if (i + 1) % 100 == 0 or (i + 1) == len(all_tiles):
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (len(all_tiles) - i - 1) / rate if rate > 0 else 0
            print(
                f"  [{i + 1}/{len(all_tiles)}] +{downloaded} cached:{skipped} failed:{failed} ETA:{remaining:.0f}s"
            )

        if downloaded > 0:
            time.sleep(TILE_RATE_LIMIT)

    total_size = sum(f.stat().st_size for f in tile_dir.rglob("*.png"))
    print(f"\n✓ Tiles: {downloaded} new, {skipped} cached, {failed} failed")
    print(f"  Size: {total_size / (1024*1024):.1f} MB")

    return str(tile_dir)


# ============================================================================
# GRAPH FUNCTIONS
# ============================================================================


def networkx_to_networkit(G_nx):
    """Convert NetworkX graph to NetworKit graph."""
    node_mapping = {node: i for i, node in enumerate(G_nx.nodes())}
    reverse_mapping = {i: node for node, i in node_mapping.items()}

    n = len(G_nx.nodes())
    G_nk = nk.Graph(n, weighted=True, directed=False)

    for u, v, data in G_nx.edges(data=True):
        weight = data.get("length", 1.0)
        G_nk.addEdge(node_mapping[u], node_mapping[v], weight)

    return G_nk, node_mapping, reverse_mapping


def save_graph(G_nx, G_nk, node_mapping, reverse_mapping, output_dir, slug):
    """Save graphs in optimized formats."""
    print(f"\nSaving graphs...")

    graphml_path = output_dir / f"{slug}.graphml"
    ox.save_graphml(G_nx, graphml_path)

    nkb_path = output_dir / f"{slug}.nkb"
    nk.graphio.writeGraph(G_nk, str(nkb_path), nk.Format.NetworkitBinary)

    mapping_path = output_dir / f"{slug}_mappings.json"
    with open(mapping_path, "w") as f:
        json.dump({"nx_to_nk": node_mapping, "nk_to_nx": reverse_mapping}, f)

    print(f"  ✓ {slug}.graphml: {graphml_path.stat().st_size / 1024 / 1024:.1f} MB")
    print(f"  ✓ {slug}.nkb: {nkb_path.stat().st_size / 1024 / 1024:.1f} MB")


# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================


def export_nodes_to_duckdb(G_nx, db_path):
    """Export node coordinates to DuckDB."""
    print("\n" + "=" * 70)
    print("EXPORTING NODES TO DUCKDB")
    print("=" * 70)

    con = duckdb.connect(str(db_path))
    con.install_extension("spatial")
    con.load_extension("spatial")

    nodes_data = [
        (node, data["y"], data["x"], data["x"], data["y"])
        for node, data in G_nx.nodes(data=True)
        if "y" in data and "x" in data
    ]

    print(f"✓ Extracted {len(nodes_data):,} nodes")

    con.execute("DROP TABLE IF EXISTS nodes")
    con.execute(
        """
        CREATE TABLE nodes (
            node_id BIGINT PRIMARY KEY, lat DOUBLE, lon DOUBLE, geom GEOMETRY
        )
    """
    )
    con.executemany("INSERT INTO nodes VALUES (?, ?, ?, ST_Point(?, ?))", nodes_data)
    con.execute("CREATE INDEX nodes_geom_idx ON nodes USING RTREE (geom)")
    con.close()


def download_osm_features(place_name):
    """Download humanitarian-relevant OSM features. Falls back to chunked queries for large areas."""
    print("\n" + "=" * 70)
    print("DOWNLOADING OSM FEATURES")
    print("=" * 70)

    print(f"\nTags: {', '.join(OSM_TAGS.keys())}")

    # Try single combined query first (fastest for smaller areas)
    print("Attempting single query... ", end="", flush=True)
    start = time.time()

    try:
        gdf = ox.features_from_place(place_name, tags=OSM_TAGS)
        print(f"✓ {len(gdf):,} features ({time.time()-start:.1f}s)")
        return _process_features(gdf)

    except Exception as e:
        if "too long" in str(e).lower() or "16 MB" in str(e):
            print(f"too large, chunking...")
        else:
            print(f"failed: {str(e)[:50]}")
            print("Falling back to chunked queries...")

    # Fall back to separate queries per tag type
    all_gdfs = []
    for tag_key, tag_values in OSM_TAGS.items():
        print(f"  {tag_key}... ", end="", flush=True)
        start = time.time()

        try:
            if tag_values is True:
                tags = {tag_key: True}
            else:
                tags = {tag_key: tag_values}

            gdf = ox.features_from_place(place_name, tags=tags)
            all_gdfs.append(gdf)
            print(f"✓ {len(gdf):,} ({time.time()-start:.1f}s)")

        except Exception as e:
            print(f"✗ {str(e)[:40]}")

    if not all_gdfs:
        print("No features downloaded!")
        return []

    # Combine all GeoDataFrames
    combined = pd.concat(all_gdfs, ignore_index=True)
    print(f"\n✓ Total: {len(combined):,} features")

    return _process_features(combined)


def _process_features(gdf):
    """Process GeoDataFrame into list of feature dicts with deduplication."""
    if len(gdf) == 0:
        return []

    # Project to UTM for accurate centroid
    gdf_proj = gdf.to_crs(gdf.estimate_utm_crs())
    gdf["centroid"] = gdf_proj.geometry.centroid.to_crs("EPSG:4326")
    gdf["lat"] = gdf["centroid"].y
    gdf["lon"] = gdf["centroid"].x

    # Extract tag_key and tag_value from whichever column is present
    def get_tag_info(row):
        for key in OSM_TAGS.keys():
            if key in row.index and pd.notna(row[key]):
                return key, str(row[key])
        return "other", "yes"

    tag_info = gdf.apply(get_tag_info, axis=1)
    gdf["tag_key"] = [t[0] for t in tag_info]
    gdf["tag_value"] = [t[1] for t in tag_info]

    cols = ["lat", "lon", "name", "tag_key", "tag_value"]
    cols = [c for c in cols if c in gdf.columns]

    result = gdf[cols].to_dict("records")

    # Deduplicate: same name + same location (within ~10m)
    before_count = len(result)
    seen = set()
    deduped = []
    for r in result:
        # Round to 4 decimal places (~11m precision)
        key = (r.get("name"), round(r["lat"], 4), round(r["lon"], 4), r["tag_value"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    removed = before_count - len(deduped)
    print(f"✓ Processed {len(deduped):,} features ({removed:,} duplicates removed)")

    return deduped


def download_places(place_name):
    """Download neighborhood/suburb/locality names for geocoding."""
    print("\n" + "=" * 70)
    print("DOWNLOADING PLACE NAMES")
    print("=" * 70)

    print(f"\nTags: {', '.join(PLACE_TAGS.keys())}")

    try:
        gdf = ox.features_from_place(place_name, tags=PLACE_TAGS)
        print(f"✓ {len(gdf):,} places found")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return []

    if len(gdf) == 0:
        return []

    # Get centroids
    gdf_proj = gdf.to_crs(gdf.estimate_utm_crs())
    gdf["centroid"] = gdf_proj.geometry.centroid.to_crs("EPSG:4326")
    gdf["lat"] = gdf["centroid"].y
    gdf["lon"] = gdf["centroid"].x

    # Extract place type
    def get_place_type(row):
        if "place" in row.index and pd.notna(row["place"]):
            return str(row["place"])
        return "unknown"

    gdf["place_type"] = gdf.apply(get_place_type, axis=1)

    # Filter to rows with names
    gdf = gdf[gdf["name"].notna()].copy()

    places = []
    seen = set()
    for _, row in gdf.iterrows():
        name = row["name"]
        # Dedupe by name (case-insensitive)
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        places.append(
            {
                "name": name,
                "lat": row["lat"],
                "lon": row["lon"],
                "place_type": row["place_type"],
            }
        )

    print(f"✓ {len(places):,} unique places")

    # Show some examples
    for p in places[:10]:
        print(f"  • {p['name']} ({p['place_type']})")
    if len(places) > 10:
        print(f"  ... and {len(places) - 10} more")

    return places


def load_places_to_duckdb(places, db_path):
    """Load place names into DuckDB for geocoding."""
    print("\n" + "=" * 70)
    print("LOADING PLACES INTO DUCKDB")
    print("=" * 70)

    con = duckdb.connect(str(db_path))
    con.install_extension("spatial")
    con.load_extension("spatial")

    con.execute("DROP TABLE IF EXISTS places")

    if len(places) == 0:
        con.execute(
            """
            CREATE TABLE places (
                name VARCHAR, lat DOUBLE, lon DOUBLE, 
                place_type VARCHAR, name_lower VARCHAR
            )
        """
        )
        print("⚠️ No places to load (empty table created)")
        con.close()
        return 0

    df = pd.DataFrame(places)
    df["name_lower"] = df["name"].str.lower()

    con.execute("CREATE TABLE places AS SELECT * FROM df")
    con.execute("CREATE INDEX places_name_idx ON places(name_lower)")

    print(f"✓ Loaded {len(places):,} places")

    con.close()
    return len(places)


def load_features_to_duckdb(features, db_path):
    """Load features into DuckDB."""
    print("\n" + "=" * 70)
    print("LOADING FEATURES INTO DUCKDB")
    print("=" * 70)

    con = duckdb.connect(str(db_path))
    con.install_extension("spatial")
    con.load_extension("spatial")

    con.execute("DROP TABLE IF EXISTS osm_features")

    print(f"\nTotal features: {len(features):,}")

    if len(features) == 0:
        # Create empty table with correct schema
        con.execute(
            """
            CREATE TABLE osm_features (
                lat DOUBLE, lon DOUBLE, name VARCHAR, 
                tag_key VARCHAR, tag_value VARCHAR, geom GEOMETRY
            )
        """
        )
        con.execute(
            "CREATE INDEX osm_features_geom_idx ON osm_features USING RTREE (geom)"
        )
        con.execute(
            "CREATE INDEX osm_features_tag_idx ON osm_features(tag_key, tag_value)"
        )
        print("⚠️ No features to load (empty table created)")
        con.close()
        return 0

    df = pd.DataFrame(features)

    # Ensure required columns exist
    if "name" not in df.columns:
        df["name"] = None

    con.execute("CREATE TABLE osm_features AS SELECT * FROM df")
    con.execute("ALTER TABLE osm_features ADD COLUMN geom GEOMETRY")
    con.execute(
        "UPDATE osm_features SET geom = ST_Point(lon, lat) WHERE lon IS NOT NULL"
    )
    con.execute("CREATE INDEX osm_features_geom_idx ON osm_features USING RTREE (geom)")
    con.execute("CREATE INDEX osm_features_tag_idx ON osm_features(tag_key, tag_value)")

    # Stats by tag
    print("\nFeatures by type:")
    result = con.execute(
        """
        SELECT tag_key, tag_value, COUNT(*) as cnt 
        FROM osm_features 
        GROUP BY tag_key, tag_value 
        HAVING cnt > 10
        ORDER BY cnt DESC 
        LIMIT 20
    """
    ).fetchall()

    for row in result:
        print(f"  {row[0]}={row[1]}: {row[2]:,}")

    total = con.execute("SELECT COUNT(*) FROM osm_features").fetchone()[0]
    print(f"\n  TOTAL: {total:,}")

    con.close()
    return total


# ============================================================================
# CONFIG & SETUP
# ============================================================================


def save_config(output_dir, slug, location_name, G_nx, poi_count, place_count):
    """Save location config."""
    bounds = get_graph_bounds(G_nx)
    center = get_graph_center(G_nx)

    config = {
        "slug": slug,
        "name": location_name,
        "center": center,
        "bounds": bounds,
        "nodes": G_nx.number_of_nodes(),
        "edges": G_nx.number_of_edges(),
        "pois": poi_count,
        "places": place_count,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    config_path = output_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  ✓ config.json")


# ============================================================================
# MAIN
# ============================================================================


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nExamples:")
        print('  python build_location.py "Dhaka, Bangladesh" dhaka')
        print('  python build_location.py "Mandalay, Myanmar" mandalay')
        print(
            '  python build_location.py "Dhaka, Bangladesh" dhaka --tiles  # include offline tiles'
        )
        sys.exit(1)

    location_name = sys.argv[1]
    slug = sys.argv[2].lower().replace(" ", "_").replace("'", "")
    download_tiles_flag = "--tiles" in sys.argv

    print("\n" + "=" * 70)
    print("DREAM MERIDIAN - LOCATION BUILDER")
    print("=" * 70)
    print(f"\nLocation: {location_name}")
    print(f"Data:     data/{slug}/")
    if download_tiles_flag:
        print(f"Tiles:    static/tiles/{slug}/")
    else:
        print(f"Tiles:    Using online tiles (use --tiles flag for offline)")
    print("=" * 70)

    # Create directories
    output_dir = Path("data") / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    total_start = time.time()

    # [1/5] Street network
    print("\n[1/5] Downloading street network...")
    start = time.time()
    G_nx = ox.graph_from_place(location_name, network_type="all", simplify=True)
    print(
        f"✓ {G_nx.number_of_nodes():,} nodes, {G_nx.number_of_edges():,} edges ({time.time()-start:.1f}s)"
    )

    bounds = get_graph_bounds(G_nx)

    # [2/5] Convert graph
    print("\n[2/5] Converting to NetworKit...")
    G_nk, node_mapping, reverse_mapping = networkx_to_networkit(G_nx)
    save_graph(G_nx, G_nk, node_mapping, reverse_mapping, output_dir, slug)

    # [3/5] Export nodes
    print("\n[3/5] Building spatial database...")
    db_path = output_dir / f"{slug}.duckdb"
    export_nodes_to_duckdb(G_nx, db_path)

    # [4/5] POI features
    print("\n[4/5] Downloading humanitarian POI features...")
    features = download_osm_features(location_name)
    poi_count = load_features_to_duckdb(features, db_path)

    # [5/5] Place names for geocoding
    print("\n[5/5] Downloading place names for geocoding...")
    places = download_places(location_name)
    place_count = load_places_to_duckdb(places, db_path)

    # Optional: Map tiles
    if download_tiles_flag:
        print("\n[+] Downloading map tiles (this may take a while)...")
        download_tiles(bounds, slug)

    # Save config
    print("\nFinalizing...")
    save_config(output_dir, slug, location_name, G_nx, poi_count, place_count)

    total_time = time.time() - total_start

    # Summary
    print("\n" + "=" * 70)
    print("BUILD COMPLETE")
    print("=" * 70)

    tiles_info = (
        f"static/tiles/{slug}/          (offline map tiles)"
        if download_tiles_flag
        else "(using online tiles)"
    )

    print(
        f"""
Location: {location_name}

Files:
  data/{slug}/
    ├── {slug}.nkb              (road network)
    ├── {slug}.duckdb           (spatial database)
    ├── {slug}_mappings.json    (node mappings)
    └── config.json             (metadata)
  
  {tiles_info}

Stats:
  Nodes:  {G_nk.numberOfNodes():,}
  Edges:  {G_nk.numberOfEdges():,}
  POIs:   {poi_count:,}
  Places: {place_count:,}
  Time:   {total_time/60:.1f} minutes

✅ Ready! Run: streamlit run app.py
"""
    )


if __name__ == "__main__":
    main()

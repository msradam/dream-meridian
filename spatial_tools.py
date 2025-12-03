"""
./spatial_tools.py
DreamMeridian - Spatial Tools
Multi-location support: load_location("dhaka") loads data/dhaka/*
"""

import networkit as nk
import duckdb
import json
from pathlib import Path
from math import sqrt, cos, radians

# ============================================================================
# Global State (populated by load_location)
# ============================================================================
G_nk = None
node_mapping = {}
reverse_mapping = {}
con = None
current_location = None

# ============================================================================
# Location Loading
# ============================================================================


def get_available_locations() -> dict:
    """Discover all built locations."""
    locations = {}
    for config_path in Path("data").glob("*/config.json"):
        try:
            with open(config_path) as f:
                config = json.load(f)
                locations[config["slug"]] = {
                    "name": config["name"],
                    "center": config["center"],
                    "nodes": config.get("nodes", 0),
                    "pois": config.get("pois", 0),
                    "path": config_path.parent,
                }
        except:
            continue
    return locations


def load_location(slug: str):
    """Load a location by slug."""
    global G_nk, node_mapping, reverse_mapping, con, current_location

    if current_location == slug and G_nk is not None:
        return

    base_path = Path("data") / slug

    if not base_path.exists():
        raise FileNotFoundError(f"Location not found: {base_path}")

    print(f"Loading {slug}...")

    graph_path = base_path / f"{slug}.nkb"
    G_nk = nk.graphio.readGraph(str(graph_path), nk.Format.NetworkitBinary)
    print(f"  ✓ Graph: {G_nk.numberOfNodes():,} nodes, {G_nk.numberOfEdges():,} edges")

    mappings_path = base_path / f"{slug}_mappings.json"
    with open(mappings_path, "r") as f:
        mappings = json.load(f)
        node_mapping = {int(k): v for k, v in mappings["nx_to_nk"].items()}
        reverse_mapping = {int(k): v for k, v in mappings["nk_to_nx"].items()}

    db_path = base_path / f"{slug}.duckdb"
    if con is not None:
        con.close()
    con = duckdb.connect(str(db_path), read_only=True)
    con.install_extension("spatial")
    con.load_extension("spatial")

    poi_count = con.execute("SELECT COUNT(*) FROM osm_features").fetchone()[0]
    print(f"  ✓ Database: {poi_count:,} POIs")

    current_location = slug
    print(f"  ✓ Ready: {slug}")


# ============================================================================
# Helper Functions
# ============================================================================


def find_nearest_node(lat: float, lon: float) -> tuple:
    """Find nearest graph node to a lat/lon point."""
    result = con.execute(
        """
        SELECT node_id, lat, lon
        FROM nodes
        ORDER BY ST_Distance(geom, ST_Point(?, ?))
        LIMIT 1
    """,
        [lon, lat],
    ).fetchone()
    return result


def _extract_path_coords(path_nk: list, sample_size: int = 100) -> list:
    """Extract lat/lon coordinates from a NetworKit path."""
    if not path_nk:
        return []

    step = max(1, len(path_nk) // sample_size)
    path_coords = []

    for i in range(0, len(path_nk), step):
        nx_id = reverse_mapping.get(path_nk[i])
        if nx_id:
            node_data = con.execute(
                "SELECT lat, lon FROM nodes WHERE node_id = ?", [nx_id]
            ).fetchone()
            if node_data:
                path_coords.append({"lat": node_data[0], "lon": node_data[1]})

    # Always include last node
    nx_id = reverse_mapping.get(path_nk[-1])
    if nx_id:
        node_data = con.execute(
            "SELECT lat, lon FROM nodes WHERE node_id = ?", [nx_id]
        ).fetchone()
        if node_data:
            last = {"lat": node_data[0], "lon": node_data[1]}
            if not path_coords or path_coords[-1] != last:
                path_coords.append(last)

    return path_coords


# ============================================================================
# Spatial Queries
# ============================================================================


def list_pois(poi_type: str, lat: float, lon: float, radius_m: int = 1000) -> str:
    """List POIs of a given type within radius, with total count."""
    total = con.execute(
        """
        SELECT COUNT(*)
        FROM osm_features
        WHERE tag_value = ?
          AND ST_Distance(geom, ST_Point(?, ?)) * 111000 < ?
    """,
        [poi_type, lon, lat, radius_m],
    ).fetchone()[0]

    results = con.execute(
        """
        SELECT name, lat, lon,
               ST_Distance(geom, ST_Point(?, ?)) * 111000 as distance_m
        FROM osm_features
        WHERE tag_value = ?
          AND ST_Distance(geom, ST_Point(?, ?)) * 111000 < ?
        ORDER BY distance_m
        LIMIT 50
    """,
        [lon, lat, poi_type, lon, lat, radius_m],
    ).fetchall()

    return json.dumps(
        {
            "poi_type": poi_type,
            "count": total,
            "radius_m": radius_m,
            "center": {"lat": lat, "lon": lon},
            "pois": [
                {"name": r[0], "lat": r[1], "lon": r[2], "distance_m": r[3]}
                for r in results
            ],
        }
    )


def find_nearest_poi_with_route(
    poi_type: str,
    lat: float,
    lon: float,
    limit: int = 3,
    distance: int = None,
    radius_m: int = None,
) -> str:
    """Find nearest POIs and calculate walking routes to each, including path to nearest."""
    search_radius = distance or radius_m

    if search_radius:
        pois = con.execute(
            """
            SELECT name, lat, lon
            FROM osm_features
            WHERE tag_value = ?
              AND name IS NOT NULL
              AND ST_Distance(geom, ST_Point(?, ?)) * 111000 < ?
            ORDER BY ST_Distance(geom, ST_Point(?, ?))
            LIMIT ?
        """,
            [poi_type, lon, lat, search_radius, lon, lat, limit],
        ).fetchall()
    else:
        pois = con.execute(
            """
            SELECT name, lat, lon
            FROM osm_features
            WHERE tag_value = ?
              AND name IS NOT NULL
            ORDER BY ST_Distance(geom, ST_Point(?, ?))
            LIMIT ?
        """,
            [poi_type, lon, lat, limit],
        ).fetchall()

    if not pois:
        return json.dumps({"poi_type": poi_type, "found": 0, "nearest_pois": []})

    start_node = find_nearest_node(lat, lon)
    start_nk = node_mapping.get(start_node[0])

    results = []
    nearest_path = []  # Store path to nearest POI

    for idx, (name, poi_lat, poi_lon) in enumerate(pois):
        end_node = find_nearest_node(poi_lat, poi_lon)
        end_nk = node_mapping.get(end_node[0])

        if start_nk is None or end_nk is None:
            continue

        # For first POI, get full path; for others just distance
        store_path = idx == 0
        dijkstra = nk.distance.Dijkstra(G_nk, start_nk, True, store_path, end_nk)
        dijkstra.run()

        distance_m = dijkstra.distance(end_nk)
        if distance_m < float("inf"):
            walk_minutes = distance_m / 83.33

            poi_data = {
                "name": name,
                "lat": poi_lat,
                "lon": poi_lon,
                "distance_m": round(distance_m, 1),
                "walk_minutes": round(walk_minutes, 1),
            }

            # Extract path for nearest POI
            if store_path and not nearest_path:
                path_nk = dijkstra.getPath(end_nk)
                nearest_path = _extract_path_coords(path_nk)

            results.append(poi_data)

    results.sort(key=lambda x: x["walk_minutes"])

    return json.dumps(
        {
            "poi_type": poi_type,
            "found": len(results),
            "nearest_pois": results,
            "path": nearest_path,  # Path to nearest POI
            "start": {"lat": lat, "lon": lon},
        }
    )


def calculate_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> str:
    """Calculate walking route between two points."""
    start_node = find_nearest_node(start_lat, start_lon)
    end_node = find_nearest_node(end_lat, end_lon)

    start_nk = node_mapping.get(start_node[0])
    end_nk = node_mapping.get(end_node[0])

    if start_nk is None or end_nk is None:
        return json.dumps({"error": "Could not find route nodes"})

    dijkstra = nk.distance.Dijkstra(G_nk, start_nk, True, True, end_nk)
    dijkstra.run()

    distance_m = dijkstra.distance(end_nk)
    if distance_m == float("inf"):
        return json.dumps({"error": "No route found"})

    path_nk = dijkstra.getPath(end_nk)
    path_coords = _extract_path_coords(path_nk)

    return json.dumps(
        {
            "distance_km": round(distance_m / 1000, 2),
            "walk_minutes": round(distance_m / 83.33, 0),
            "num_nodes": len(path_nk),
            "path": path_coords,
        }
    )


def find_along_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    poi_type: str = None,
    buffer_m: int = 100,
) -> str:
    """Find POIs along a walking route between two points."""
    start_node = find_nearest_node(start_lat, start_lon)
    end_node = find_nearest_node(end_lat, end_lon)

    start_nk = node_mapping.get(start_node[0])
    end_nk = node_mapping.get(end_node[0])

    if start_nk is None or end_nk is None:
        return json.dumps({"error": "Could not find route nodes"})

    dijkstra = nk.distance.Dijkstra(G_nk, start_nk, True, True, end_nk)
    dijkstra.run()

    distance_m = dijkstra.distance(end_nk)
    if distance_m == float("inf"):
        return json.dumps({"error": "No route found"})

    path_nk = dijkstra.getPath(end_nk)

    # Extract full path coordinates
    path_coords = []
    for nk_id in path_nk:
        nx_id = reverse_mapping.get(nk_id)
        if nx_id:
            node_data = con.execute(
                "SELECT lat, lon FROM nodes WHERE node_id = ?", [nx_id]
            ).fetchone()
            if node_data:
                path_coords.append((node_data[0], node_data[1]))

    if len(path_coords) < 2:
        return json.dumps({"error": "Route too short"})

    # Sample path for efficient distance calculations
    sample_step = max(1, len(path_coords) // 40)
    sampled = path_coords[::sample_step]
    if path_coords[-1] not in sampled:
        sampled.append(path_coords[-1])

    # Build bounding box
    lats = [p[0] for p in path_coords]
    lons = [p[1] for p in path_coords]
    buffer_deg = buffer_m / 111000 * 1.5

    min_lat, max_lat = min(lats) - buffer_deg, max(lats) + buffer_deg
    min_lon, max_lon = min(lons) - buffer_deg, max(lons) + buffer_deg

    # Query candidate POIs
    type_filter = "AND tag_value = ?" if poi_type else ""
    params = [min_lon, max_lon, min_lat, max_lat]
    if poi_type:
        params.append(poi_type)

    candidates = con.execute(
        f"""
        SELECT name, lat, lon, tag_key, tag_value
        FROM osm_features
        WHERE lon BETWEEN ? AND ?
          AND lat BETWEEN ? AND ?
          AND name IS NOT NULL
          {type_filter}
    """,
        params,
    ).fetchall()

    # Filter to POIs within buffer
    mid_lat = (min_lat + max_lat) / 2
    cos_lat = cos(radians(mid_lat))

    def min_distance_to_route(poi_lat, poi_lon):
        min_dist = float("inf")
        for lat, lon in sampled:
            dlat = (poi_lat - lat) * 111000
            dlon = (poi_lon - lon) * 111000 * cos_lat
            dist = sqrt(dlat * dlat + dlon * dlon)
            if dist < min_dist:
                min_dist = dist
        return min_dist

    def distance_along_route(poi_lat, poi_lon):
        best_idx, best_dist = 0, float("inf")
        for i, (lat, lon) in enumerate(sampled):
            dlat = (poi_lat - lat) * 111000
            dlon = (poi_lon - lon) * 111000 * cos_lat
            dist = sqrt(dlat * dlat + dlon * dlon)
            if dist < best_dist:
                best_idx, best_dist = i, dist
        return best_idx

    pois_along = []
    for name, lat, lon, tag_key, tag_value in candidates:
        dist = min_distance_to_route(lat, lon)
        if dist <= buffer_m:
            pois_along.append(
                {
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "type": tag_value,
                    "off_route_m": round(dist, 1),
                    "_order": distance_along_route(lat, lon),
                }
            )

    pois_along.sort(key=lambda p: p["_order"])
    for p in pois_along:
        del p["_order"]

    # Sample path for visualization
    vis_path = _extract_path_coords(path_nk)

    return json.dumps(
        {
            "distance_km": round(distance_m / 1000, 2),
            "walk_minutes": round(distance_m / 83.33, 0),
            "buffer_m": buffer_m,
            "poi_type": poi_type,
            "pois_found": len(pois_along),
            "pois": pois_along[:15],
            "path": vis_path,
        }
    )


def generate_isochrone(lat: float, lon: float, max_minutes: int = 15) -> str:
    """Generate walkable area from a point."""
    start_node = find_nearest_node(lat, lon)
    start_nk = node_mapping.get(start_node[0])

    if start_nk is None:
        return json.dumps({"error": "Could not find start node"})

    max_distance = max_minutes * 83.33

    dijkstra = nk.distance.Dijkstra(G_nk, start_nk, True, False)
    dijkstra.run()

    boundary_points = []
    reachable = 0

    for nk_id in range(G_nk.numberOfNodes()):
        dist = dijkstra.distance(nk_id)
        if dist <= max_distance:
            reachable += 1
            if dist > max_distance * 0.8:
                nx_id = reverse_mapping.get(nk_id)
                if nx_id:
                    node_data = con.execute(
                        "SELECT lat, lon FROM nodes WHERE node_id = ?", [nx_id]
                    ).fetchone()
                    if node_data:
                        boundary_points.append(
                            {
                                "lat": node_data[0],
                                "lon": node_data[1],
                                "walk_minutes": round(dist / 83.33, 1),
                            }
                        )

    if len(boundary_points) > 100:
        step = len(boundary_points) // 100
        boundary_points = boundary_points[::step]

    return json.dumps(
        {
            "max_minutes": max_minutes,
            "reachable_nodes": reachable,
            "boundary_points": boundary_points,
        }
    )


def geocode_place(place_name: str) -> str:
    """Get coordinates for a place name."""
    results = con.execute(
        """
        SELECT lat, lon, name
        FROM osm_features
        WHERE name ILIKE ?
        LIMIT 10
    """,
        [f"%{place_name}%"],
    ).fetchall()

    if not results:
        return json.dumps({"error": f"Place not found: {place_name}"})

    lats = [r[0] for r in results]
    lons = [r[1] for r in results]

    return json.dumps(
        {
            "place": place_name,
            "lat": sum(lats) / len(lats),
            "lon": sum(lons) / len(lons),
            "matches": len(results),
        }
    )


# ============================================================================
# Tool Executor
# ============================================================================

TOOLS = {
    "list_pois": list_pois,
    "find_nearest_poi_with_route": find_nearest_poi_with_route,
    "calculate_route": calculate_route,
    "find_along_route": find_along_route,
    "generate_isochrone": generate_isochrone,
    "geocode_place": geocode_place,
}


def execute_tool(tool_name: str, **kwargs) -> str:
    """Execute a tool by name with given arguments."""
    if tool_name not in TOOLS:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        return TOOLS[tool_name](**kwargs)
    except Exception as e:
        return json.dumps({"error": str(e)})

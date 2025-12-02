#!/usr/bin/env python3
"""
./dream-meridian.py
Dream Meridian - Offline Spatial Intelligence

Core query engine with CLI interface.

Usage:
    python dream-meridian.py "Find hospitals near Dhanmondi"
    python dream-meridian.py -l dhaka "Schools within 1km of Gulshan"
    python dream-meridian.py --list
    python dream-meridian.py --health

As a library:
    from dream_meridian import query, load_location, list_locations
"""

import argparse
import json
import sys
import time
import requests
from dataclasses import dataclass, asdict
from pathlib import Path

import spatial_tools
import geocode_layer

# ============================================================================
# Configuration
# ============================================================================

LLAMA_URL = "http://localhost:8080/v1/chat/completions"

SYSTEM_PROMPT = """Select ONE tool. Output JSON only.

Valid poi_type values: hospital, clinic, doctors, pharmacy, police, fire_station, 
shelter, school, university, bank, atm, supermarket, marketplace, drinking_water, 
water_point, fuel, bus_station, place_of_worship

Tools:
- geocode_place(place_name) - Get coordinates for a place name
- list_pois(poi_type,lat,lon,radius_m) - List POIs with count and distances
- find_nearest_poi_with_route(poi_type,lat,lon) - Nearest POIs with walking time
- generate_isochrone(lat,lon,max_minutes) - Walkable area from point
- calculate_route(start_lat,start_lon,end_lat,end_lon) - Walking route between points"""
# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class QueryResult:
    """Result of a spatial query."""
    tool_name: str
    tool_args: dict
    result: dict
    geocoded: dict
    query_time: float
    modified_query: str
    success: bool = True
    error: str = None
    
    def to_dict(self) -> dict:
        return asdict(self)

# ============================================================================
# Location Management
# ============================================================================

def list_locations() -> dict:
    """Find all built locations by scanning for config.json files."""
    locations = {}
    for config_path in Path("data").glob("*/config.json"):
        try:
            with open(config_path) as f:
                config = json.load(f)
                slug = config["slug"]
                locations[slug] = {
                    "name": config["name"],
                    "center": [config["center"]["lat"], config["center"]["lon"]],
                    "bounds": config["bounds"],
                    "nodes": config.get("nodes", 0),
                    "edges": config.get("edges", 0),
                    "pois": config.get("pois", 0)
                }
        except (json.JSONDecodeError, KeyError):
            continue
    return locations

def load_location(slug: str) -> bool:
    """Load spatial data for a location."""
    try:
        spatial_tools.load_location(slug)
        geocode_layer.load_location(slug)
        return True
    except FileNotFoundError as e:
        return False

def get_current_location() -> str:
    """Return currently loaded location slug."""
    return spatial_tools.current_location

# ============================================================================
# Health Checks
# ============================================================================

def check_llm_server(url: str = LLAMA_URL) -> dict:
    """Check if llama-server is responding."""
    health_url = url.replace('/v1/chat/completions', '/health')
    try:
        r = requests.get(health_url, timeout=2)
        return {"online": r.status_code == 200, "url": url}
    except requests.exceptions.RequestException:
        return {"online": False, "url": url}

def health_check() -> dict:
    """Full system health check."""
    locations = list_locations()
    llm = check_llm_server()
    current = get_current_location()
    
    return {
        "llm_server": llm,
        "locations_available": len(locations),
        "locations": list(locations.keys()),
        "current_location": current,
        "spatial_tools_loaded": spatial_tools.G_nk is not None,
        "database_connected": spatial_tools.con is not None
    }

# ============================================================================
# Query Processing
# ============================================================================

def query(user_query: str, location: str = None, llm_url: str = LLAMA_URL) -> QueryResult:
    """
    Process a natural language spatial query.
    
    Args:
        user_query: Natural language question
        location: Location slug (loads if different from current)
        llm_url: LLM server endpoint
    
    Returns:
        QueryResult with tool output and metadata
    """
    start_time = time.time()
    
    # Load location if specified and different
    if location and location != get_current_location():
        if not load_location(location):
            return QueryResult(
                tool_name="", tool_args={}, result={},
                geocoded={}, query_time=time.time() - start_time,
                modified_query=user_query,
                success=False, error=f"Location not found: {location}"
            )
    
    # Check if any location is loaded
    if spatial_tools.G_nk is None:
        return QueryResult(
            tool_name="", tool_args={}, result={},
            geocoded={}, query_time=time.time() - start_time,
            modified_query=user_query,
            success=False, error="No location loaded. Use load_location() first."
        )
    
    # Geocode place names in query
    try:
        modified_query, geocoded = geocode_layer.geocode_query(user_query)
    except Exception as e:
        modified_query, geocoded = user_query, {}
    
    # Call LLM for tool selection
    try:
        response = requests.post(llm_url, json={
            "model": "xLAM",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": modified_query}
            ]
        }, timeout=120)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        return QueryResult(
            tool_name="", tool_args={}, result={},
            geocoded=geocoded, query_time=time.time() - start_time,
            modified_query=modified_query,
            success=False, error="Cannot connect to LLM server. Is llama-server running?"
        )
    except requests.exceptions.Timeout:
        return QueryResult(
            tool_name="", tool_args={}, result={},
            geocoded=geocoded, query_time=time.time() - start_time,
            modified_query=modified_query,
            success=False, error="LLM request timed out."
        )
    
    # Parse LLM response
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        tool_call = json.loads(content)
        tool_name = tool_call["name"]
        tool_args = tool_call["arguments"]
    except (json.JSONDecodeError, KeyError) as e:
        return QueryResult(
            tool_name="", tool_args={}, result={"raw_response": content if 'content' in dir() else str(e)},
            geocoded=geocoded, query_time=time.time() - start_time,
            modified_query=modified_query,
            success=False, error=f"Failed to parse LLM response: {e}"
        )
    
    # Execute spatial tool
    try:
        result_json = spatial_tools.execute_tool(tool_name, **tool_args)
        result = json.loads(result_json)
    except Exception as e:
        return QueryResult(
            tool_name=tool_name, tool_args=tool_args, result={},
            geocoded=geocoded, query_time=time.time() - start_time,
            modified_query=modified_query,
            success=False, error=f"Tool execution failed: {e}"
        )
    
    return QueryResult(
        tool_name=tool_name,
        tool_args=tool_args,
        result=result,
        geocoded=geocoded,
        query_time=time.time() - start_time,
        modified_query=modified_query,
        success=True
    )

# ============================================================================
# CLI Interface
# ============================================================================

def format_result(result: QueryResult, verbose: bool = False) -> str:
    """Format QueryResult for terminal output."""
    lines = []
    
    if not result.success:
        return f"Error: {result.error}"
    
    # Header
    lines.append(f"Tool: {result.tool_name}")
    lines.append(f"Time: {result.query_time:.2f}s")
    
    if result.geocoded:
        places = ", ".join(f"{k} ({v['lat']:.4f}, {v['lon']:.4f})" for k, v in result.geocoded.items())
        lines.append(f"Geocoded: {places}")
    
    lines.append("")
    
    # Results
    data = result.result
    
    if "error" in data:
        lines.append(f"Error: {data['error']}")
    elif "count" in data:
        lines.append(f"{data.get('poi_type', 'POIs').title()}: {data['count']}")
    elif "nearest_pois" in data or "pois" in data:
        pois = data.get("nearest_pois") or data.get("pois", [])
        lines.append(f"Found {len(pois)} {data.get('poi_type', 'POIs')}:")
        for poi in pois[:10]:
            name = poi.get("name", "Unknown")
            if "walk_minutes" in poi:
                lines.append(f"  • {name} ({poi['walk_minutes']:.1f} min walk)")
            elif "distance_m" in poi:
                lines.append(f"  • {name} ({poi['distance_m']:.0f}m)")
            else:
                lines.append(f"  • {name}")
    elif "distance_km" in data:
        lines.append(f"Distance: {data['distance_km']:.2f} km")
        lines.append(f"Walking time: {data['walk_minutes']:.0f} min")
    elif "reachable_nodes" in data:
        lines.append(f"Reachable in {data['max_minutes']} min: {data['reachable_nodes']} nodes")
    
    if verbose:
        lines.append("")
        lines.append("Raw result:")
        lines.append(json.dumps(data, indent=2))
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Dream Meridian - Offline Spatial Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Find hospitals near Dhanmondi"
  %(prog)s -l dhaka "Schools within 1km of Gulshan"
  %(prog)s --location san_juan "Pharmacies near Old San Juan"
  %(prog)s --list
  %(prog)s --health
        """
    )
    
    parser.add_argument("query", nargs="?", help="Natural language spatial query")
    parser.add_argument("-l", "--location", help="Location slug (default: first available)")
    parser.add_argument("--list", action="store_true", help="List available locations")
    parser.add_argument("--health", action="store_true", help="Check system health")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output (include raw JSON)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--llm-url", default=LLAMA_URL, help="LLM server URL")
    
    args = parser.parse_args()
    
    # List locations
    if args.list:
        locations = list_locations()
        if not locations:
            print("No locations found. Run build_location.py first.")
            sys.exit(1)
        print("Available locations:")
        for slug, info in locations.items():
            print(f"  {slug}: {info['name']} ({info['nodes']:,} nodes, {info['pois']:,} POIs)")
        sys.exit(0)
    
    # Health check
    if args.health:
        health = health_check()
        if args.json:
            print(json.dumps(health, indent=2))
        else:
            llm_status = "✓ Online" if health["llm_server"]["online"] else "✗ Offline"
            print(f"LLM Server: {llm_status} ({health['llm_server']['url']})")
            print(f"Locations: {health['locations_available']} available")
            if health["locations"]:
                print(f"  {', '.join(health['locations'])}")
            print(f"Current: {health['current_location'] or 'None loaded'}")
        sys.exit(0)
    
    # Query
    if not args.query:
        parser.print_help()
        sys.exit(1)
    
    # Determine location
    location = args.location
    if not location:
        locations = list_locations()
        if not locations:
            print("Error: No locations found. Run build_location.py first.")
            sys.exit(1)
        location = list(locations.keys())[0]
    
    # Execute query
    result = query(args.query, location=location, llm_url=args.llm_url)
    
    # Output
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_result(result, verbose=args.verbose))
    
    sys.exit(0 if result.success else 1)

if __name__ == "__main__":
    main()
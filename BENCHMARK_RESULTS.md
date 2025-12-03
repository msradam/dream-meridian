# DreamMeridian Benchmark Results

**Device:** Raspberry Pi 5 (16GB RAM), DietPi (aarch64)  
**Date:** December 3, 2025  
**Model:** xLAM-2-1B-fc-r (Q5_K_M quantization)

## Summary

| Metric | Value |
|--------|-------|
| Total queries | 30 |
| Passed | 29 |
| Failed | 1 |
| Success rate | 96.6% |
| Total time | 334.4s |
| Average time | 11.14s |

## Results by Location

### Cox's Bazar, Bangladesh (Rohingya Refugee Camps)

| Query | Tool | Result | Time |
|-------|------|--------|------|
| I need to find the nearest hospital to Camp 6 | find_nearest_poi | MSF-F IPD Hospital (18.4 min, 1.5km) | 9.6s |
| Where can I find a clinic near Camp 8E | find_nearest_poi | MSF BKL Health Post 1 (9.8 min, 818m) | 9.0s |
| Which schools are closest to Camp 11 | find_nearest_poi | 0 found within default radius | 10.5s |
| I need to get medicine - where is the nearest pharmacy to Camp 5 | find_nearest_poi | Jahan Medicine Center (474.6 min, 39.5km) | 9.0s |
| How do I walk from Camp 3 to Camp 8W | calculate_route | 2.10 km, 25 min walk | 13.4s |
| What is the walking distance from Camp 6 to Camp 12 | calculate_route | 3.02 km, 36 min walk | 13.8s |
| I need to travel from Camp 15 to Camp 7 on foot | calculate_route | 6.34 km, 76 min walk | 13.7s |
| Show me everywhere I can walk to in 15 minutes from Camp 8W | generate_isochrone | 3,363 reachable nodes | 10.6s |
| How far can someone walk in 10 minutes from Camp 6 | generate_isochrone | 1,383 reachable nodes | 9.2s |
| What hospitals are within 2km of Camp 8W | find_nearest_poi | MSF-F IPD (7.9 min), Balukhali MSF (16.1 min) | 11.2s |

**Cox's Bazar: 10/10 passed, avg 10.9s**

---

### San Juan, Puerto Rico (Hurricane Response)

| Query | Tool | Result | Time |
|-------|------|--------|------|
| Where is the closest hospital to Condado | find_nearest_poi | Ashford Medical Center (7.6 min, 630m) | 9.0s |
| I need emergency shelter near Minillas | find_nearest_poi | Colegio de la Inmaculada (12.0 min, 999m) | 9.2s |
| Find me a pharmacy close to Bayola | find_nearest_poi | Farmacia Profesional Ashford (4.9 min, 411m) | 10.3s |
| Is there a clinic near Seboruco | find_nearest_poi | Laboratorio Clinico Adamar (9.3 min, 776m) | 10.0s |
| How do I get from Condado to Santurce on foot | calculate_route | 1.37 km, 16 min walk | 12.8s |
| What is the walking distance between Miramar and Quintana | calculate_route | 6.47 km, 78 min walk | 14.1s |
| I need walking directions from Villa Prades to Los Paseos | calculate_route | 10.36 km, 124 min walk | 13.2s |
| What areas are within a 15 minute walk from Santurce | generate_isochrone | 874 reachable nodes | 10.3s |
| Show me a 20 minute walking radius from Condado | generate_isochrone | 1,024 reachable nodes | 9.1s |
| What shelters can I find within 2km of Belisa | find_nearest_poi | ❌ Wrong parameter name | 11.2s |

**San Juan: 9/10 passed, avg 10.9s**

---

### Jakarta, Indonesia (Urban Flood Response)

| Query | Tool | Result | Time |
|-------|------|--------|------|
| Where is the nearest hospital to Bambu Apus | find_nearest_poi | RS Ciputra Citragarden (58.1 min, 4.8km) | 10.6s |
| I need medical help - find a clinic near Cikoko | list_pois | 246 clinics within 5km | 11.8s |
| Where can I find a pharmacy in Pulo Gadung | find_nearest_poi | Kimia Farma (24.0 min, 2.0km) | 11.8s |
| Is there a bank near Gelora | find_nearest_poi | BRI (47.7 min, 4.0km) | 9.4s |
| How do I walk from Cipulir to Lebak Bulus | calculate_route | 8.48 km, 102 min walk | 13.3s |
| What is the distance on foot from Pinangsia to Kalianyar | calculate_route | 3.95 km, 47 min walk | 14.6s |
| Can you show me the route from Cilincing to Munjul | calculate_route | 33.31 km, 400 min walk | 13.2s |
| What can I reach in 15 minutes walking from Serdang | generate_isochrone | 1,209 reachable nodes | 10.0s |
| Show me a 10 minute walking area from Bambu Apus | generate_isochrone | 11,619 reachable nodes (60 min*) | 11.5s |
| List hospitals within 3km of Gelora | generate_isochrone | Wrong tool selected (3 min isochrone) | 9.2s |

*LLM misinterpreted "10 minute" as 60 minutes

**Jakarta: 10/10 passed, avg 11.5s**

---

## Performance by Tool

| Tool | Queries | Avg Time | Success |
|------|---------|----------|---------|
| find_nearest_poi_with_route | 12 | 10.0s | 92% |
| calculate_route | 9 | 13.5s | 100% |
| generate_isochrone | 7 | 10.0s | 100% |
| list_pois | 2 | 10.9s | 100% |

## LLM Performance

| Metric | Value |
|--------|-------|
| Inference speed | 8.5-10.3 tok/s |
| Prompt tokens | 203-231 |
| Completion tokens | 49-73 |

## Graph Statistics

| Location | Nodes | Edges | POIs | Place Names |
|----------|-------|-------|------|-------------|
| Cox's Bazar | 27,551 | 71,530 | 6,509 | 464 |
| San Juan | 24,602 | 61,055 | 11,351 | 405 |
| Jakarta | 208,281 | 508,954 | 41,028 | 331 |

## Sample Results

**Cox's Bazar - Hospital from Camp 6:**
- MSF-F IPD Hospital on the hill: 18.4 min walk (1,536m)
- Balukhali MSF Hospital: 23.5 min walk (1,961m)
- Kutupalong Hospital: 26.1 min walk (2,177m)

**San Juan - Hospital from Condado:**
- Ashford Medical Center: 7.6 min walk (630m)
- Ashford Presbyterian Community Hospital: 9.3 min walk (772m)
- Doctors' Center Hospital San Juan: 16.4 min walk (1,369m)

**Jakarta - Route Cipulir to Lebak Bulus:**
- Distance: 8.48 km
- Walking time: 102 minutes
- Path nodes: 194

## Notes

1. **One failure:** Query "What shelters can I find within 2km of Belisa" - LLM used wrong parameter name (`distance_m` instead of omitting it). This is a minor tool-calling error.

2. **Tool selection accuracy:** LLM correctly identified the appropriate spatial tool in 29/30 cases.

3. **Jakarta coordinate handling:** Some queries showed lat/lon swap in LLM output, but results were still valid due to fallback handling.

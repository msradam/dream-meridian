#!/bin/bash
#===============================================================================
# DreamMeridian Benchmark Suite
# 30 natural language queries across 3 disaster response scenarios
#===============================================================================

OUT="benchmark_results_$(date +%Y%m%d_%H%M%S).txt"

echo "===============================================================================" | tee "$OUT"
echo "  DreamMeridian Benchmark Suite" | tee -a "$OUT"
echo "  Date: $(date)" | tee -a "$OUT"
echo "  Device: $(uname -n) ($(uname -m))" | tee -a "$OUT"
echo "===============================================================================" | tee -a "$OUT"
echo "" | tee -a "$OUT"

PASS=0
FAIL=0
TOTAL_TIME=0

run() {
    echo "-------------------------------------------------------------------------------" | tee -a "$OUT"
    echo "[$1] $2" | tee -a "$OUT"
    echo "-------------------------------------------------------------------------------" | tee -a "$OUT"
    START=$(date +%s.%N)
    OUTPUT=$(uv run python dream-meridian.py -l "$1" "$2" 2>&1)
    END=$(date +%s.%N)
    ELAPSED=$(echo "$END - $START" | bc)
    TOTAL_TIME=$(echo "$TOTAL_TIME + $ELAPSED" | bc)
    echo "$OUTPUT" | tee -a "$OUT"
    echo "" | tee -a "$OUT"
    echo "⏱️  Query time: ${ELAPSED}s" | tee -a "$OUT"
    echo "" | tee -a "$OUT"
    
    if echo "$OUTPUT" | grep -q "Error:"; then
        ((FAIL++))
        echo "❌ FAILED" | tee -a "$OUT"
    else
        ((PASS++))
        echo "✅ PASSED" | tee -a "$OUT"
    fi
    echo "" | tee -a "$OUT"
}

echo "===============================================================================" | tee -a "$OUT"
echo "  COX'S BAZAR, BANGLADESH - Rohingya Refugee Camp Response" | tee -a "$OUT"
echo "===============================================================================" | tee -a "$OUT"
echo "" | tee -a "$OUT"

run coxs_bazar "I need to find the nearest hospital to Camp 6"
run coxs_bazar "Where can I find a clinic near Camp 8E"
run coxs_bazar "Which schools are closest to Camp 11"
run coxs_bazar "I need to get medicine - where is the nearest pharmacy to Camp 5"
run coxs_bazar "How do I walk from Camp 3 to Camp 8W"
run coxs_bazar "What is the walking distance from Camp 6 to Camp 12"
run coxs_bazar "I need to travel from Camp 15 to Camp 7 on foot"
run coxs_bazar "Show me everywhere I can walk to in 15 minutes from Camp 8W"
run coxs_bazar "How far can someone walk in 10 minutes from Camp 6"
run coxs_bazar "What hospitals are within 2km of Camp 8W"

echo "===============================================================================" | tee -a "$OUT"
echo "  SAN JUAN, PUERTO RICO - Hurricane Emergency Response" | tee -a "$OUT"
echo "===============================================================================" | tee -a "$OUT"
echo "" | tee -a "$OUT"

run san_juan "Where is the closest hospital to Condado"
run san_juan "I need emergency shelter near Minillas"
run san_juan "Find me a pharmacy close to Bayola"
run san_juan "Is there a clinic near Seboruco"
run san_juan "How do I get from Condado to Santurce on foot"
run san_juan "What is the walking distance between Miramar and Quintana"
run san_juan "I need walking directions from Villa Prades to Los Paseos"
run san_juan "What areas are within a 15 minute walk from Santurce"
run san_juan "Show me a 20 minute walking radius from Condado"
run san_juan "What shelters can I find within 2km of Belisa"

echo "===============================================================================" | tee -a "$OUT"
echo "  JAKARTA, INDONESIA - Urban Flood Response" | tee -a "$OUT"
echo "===============================================================================" | tee -a "$OUT"
echo "" | tee -a "$OUT"

run jakarta "Where is the nearest hospital to Bambu Apus"
run jakarta "I need medical help - find a clinic near Cikoko"
run jakarta "Where can I find a pharmacy in Pulo Gadung"
run jakarta "Is there a bank near Gelora"
run jakarta "How do I walk from Cipulir to Lebak Bulus"
run jakarta "What is the distance on foot from Pinangsia to Kalianyar"
run jakarta "Can you show me the route from Cilincing to Munjul"
run jakarta "What can I reach in 15 minutes walking from Serdang"
run jakarta "Show me a 10 minute walking area from Bambu Apus"
run jakarta "List hospitals within 3km of Gelora"

echo "===============================================================================" | tee -a "$OUT"
echo "  BENCHMARK SUMMARY" | tee -a "$OUT"
echo "===============================================================================" | tee -a "$OUT"
echo "" | tee -a "$OUT"

TOTAL=$((PASS + FAIL))
AVG_TIME=$(echo "scale=2; $TOTAL_TIME / $TOTAL" | bc)
SUCCESS_RATE=$(echo "scale=1; $PASS * 100 / $TOTAL" | bc)

echo "  Total queries:    $TOTAL" | tee -a "$OUT"
echo "  Passed:           $PASS" | tee -a "$OUT"
echo "  Failed:           $FAIL" | tee -a "$OUT"
echo "  Success rate:     ${SUCCESS_RATE}%" | tee -a "$OUT"
echo "  Total time:       ${TOTAL_TIME}s" | tee -a "$OUT"
echo "  Average time:     ${AVG_TIME}s" | tee -a "$OUT"
echo "" | tee -a "$OUT"
echo "  Results saved to: $OUT" | tee -a "$OUT"
echo "===============================================================================" | tee -a "$OUT"

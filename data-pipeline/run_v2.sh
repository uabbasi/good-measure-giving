#!/bin/bash
#
# V2 Pipeline - Full pipeline execution wrapper
#
# Runs all 5 phases of the V2 pipeline:
#   1. crawl.py     - Fetch raw data from all sources
#   2. extract.py   - Parse raw_html into validated schemas
#   3. synthesize.py - Aggregate and derive fields
#   4. baseline.py  - Generate AMAL scores and narratives
#   5. export.py    - Export to website JSON
#
# Usage:
#   ./run_v2.sh                          # Run with defaults (pilot_charities.txt)
#   ./run_v2.sh --charities my_list.txt  # Custom charities file
#   ./run_v2.sh --workers 5              # Custom worker count
#

set -e  # Exit on error

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default values
CHARITIES="pilot_charities.txt"
WORKERS=10

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --charities)
            CHARITIES="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --charities FILE  Charities file (default: pilot_charities.txt)"
            echo "  --workers N       Number of workers (default: 10)"
            echo "  --help            Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           V2 PIPELINE - FULL EXECUTION                   ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Charities: $CHARITIES"
echo "║  Workers:   $WORKERS"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

START_TIME=$(date +%s)

# Phase 1: Crawl
echo ""
echo "▶ PHASE 1/5: Crawl"
echo "────────────────────────────────────────────────────────────"
uv run python crawl.py --charities "$CHARITIES" --workers "$WORKERS"

# Phase 2: Extract
echo ""
echo "▶ PHASE 2/5: Extract"
echo "────────────────────────────────────────────────────────────"
uv run python extract.py --charities "$CHARITIES" --workers 5

# Phase 3: Synthesize
echo ""
echo "▶ PHASE 3/5: Synthesize"
echo "────────────────────────────────────────────────────────────"
uv run python synthesize.py --charities "$CHARITIES"

# Phase 4: Baseline
echo ""
echo "▶ PHASE 4/5: Baseline"
echo "────────────────────────────────────────────────────────────"
uv run python baseline.py --charities "$CHARITIES"

# Phase 5: Export
echo ""
echo "▶ PHASE 5/5: Export"
echo "────────────────────────────────────────────────────────────"
uv run python export.py --charities "$CHARITIES"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           V2 PIPELINE - COMPLETE                         ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Duration: ${MINUTES}m ${SECONDS}s"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

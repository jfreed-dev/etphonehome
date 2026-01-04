#!/bin/bash
# ET Phone Home - Master Lint Script
# Runs all linting tools for Python and shell scripts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0

echo "=== ET Phone Home Linting ==="
echo

# Python linting with ruff
echo -e "${YELLOW}[1/3] Running ruff...${NC}"
if ruff check client/ server/ shared/ scripts/; then
    echo -e "${GREEN}  ruff: PASSED${NC}"
else
    echo -e "${RED}  ruff: FAILED${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo

# Python formatting check with black
echo -e "${YELLOW}[2/3] Running black --check...${NC}"
if black --check client/ server/ shared/ scripts/; then
    echo -e "${GREEN}  black: PASSED${NC}"
else
    echo -e "${RED}  black: FAILED (run 'black .' to fix)${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo

# Shell script linting with shellcheck
echo -e "${YELLOW}[3/3] Running shellcheck...${NC}"
SHELL_SCRIPTS=$(find build/portable build/pyinstaller scripts -name "*.sh" 2>/dev/null || true)
if [ -n "$SHELL_SCRIPTS" ]; then
    if echo "$SHELL_SCRIPTS" | xargs shellcheck; then
        echo -e "${GREEN}  shellcheck: PASSED${NC}"
    else
        echo -e "${RED}  shellcheck: FAILED${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${YELLOW}  shellcheck: No shell scripts found${NC}"
fi
echo

# Summary
echo "=== Summary ==="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}All checks passed!${NC}"
    exit 0
else
    echo -e "${RED}$ERRORS check(s) failed${NC}"
    exit 1
fi

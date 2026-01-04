#!/bin/bash
# ET Phone Home - Security Check Script
# Runs security scanning tools: bandit, pip-audit, detect-secrets

# Don't use set -e as tools may return non-zero for non-critical issues

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ERRORS=0

echo "=== ET Phone Home Security Checks ==="
echo

# Check for required tools
check_tool() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}Error: $1 not found. Install with: pip install $1${NC}"
        exit 1
    fi
}

check_tool bandit
check_tool pip-audit
check_tool detect-secrets

# 1. Bandit - Python security linter
echo -e "${YELLOW}[1/3] Running bandit (Python security)...${NC}"
# -iii = only high severity, -q = quiet (no output on success)
BANDIT_OUTPUT=$(bandit -r client/ server/ shared/ -iii -f json 2>&1)
BANDIT_HIGH=$(echo "$BANDIT_OUTPUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len([r for r in d.get('results', []) if r['issue_severity'] == 'HIGH']))" 2>/dev/null || echo "0")
if [ "$BANDIT_HIGH" = "0" ]; then
    echo -e "${GREEN}  bandit: PASSED (no high-severity issues)${NC}"
else
    echo -e "${RED}  bandit: FAILED ($BANDIT_HIGH high-severity issue(s) found)${NC}"
    echo "$BANDIT_OUTPUT" | python3 -c "import sys, json; d=json.load(sys.stdin); [print(f'    {r[\"filename\"]}:{r[\"line_number\"]}: {r[\"issue_text\"]}') for r in d.get('results', []) if r['issue_severity'] == 'HIGH']" 2>/dev/null || true
    ERRORS=$((ERRORS + 1))
fi
echo

# 2. pip-audit - Dependency vulnerability scanning
echo -e "${YELLOW}[2/3] Running pip-audit (dependency vulnerabilities)...${NC}"
# Check project dependencies: paramiko, pyyaml, cryptography
TMP_REQ=$(mktemp)
for dep in paramiko pyyaml cryptography; do
    VER=$(pip show "$dep" 2>/dev/null | grep "^Version:" | awk '{print $2}')
    if [ -n "$VER" ]; then
        echo "$dep==$VER" >> "$TMP_REQ"
    fi
done
if [ -s "$TMP_REQ" ]; then
    if pip-audit -r "$TMP_REQ" 2>&1; then
        echo -e "${GREEN}  pip-audit: PASSED${NC}"
    else
        echo -e "${RED}  pip-audit: FAILED (vulnerabilities found)${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${YELLOW}  pip-audit: SKIPPED (dependencies not installed)${NC}"
fi
rm -f "$TMP_REQ"
echo

# 3. detect-secrets - Hardcoded secret detection
echo -e "${YELLOW}[3/3] Running detect-secrets...${NC}"
SECRETS_OUTPUT=$(detect-secrets scan --exclude-files '\.git/' --exclude-files '\.pyc$' --exclude-files '__pycache__' 2>&1)
SECRETS_COUNT=$(echo "$SECRETS_OUTPUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('results', {})))" 2>/dev/null || echo "0")
if [ "$SECRETS_COUNT" = "0" ]; then
    echo -e "${GREEN}  detect-secrets: PASSED${NC}"
else
    echo -e "${RED}  detect-secrets: FAILED ($SECRETS_COUNT potential secret(s) found)${NC}"
    echo "$SECRETS_OUTPUT" | python3 -c "import sys, json; d=json.load(sys.stdin); [print(f'    {f}: {[s[\"type\"] for s in secrets]}') for f, secrets in d.get('results', {}).items()]" 2>/dev/null || true
    ERRORS=$((ERRORS + 1))
fi
echo

# Summary
echo "=== Summary ==="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}All security checks passed!${NC}"
    exit 0
else
    echo -e "${RED}$ERRORS security check(s) failed${NC}"
    exit 1
fi

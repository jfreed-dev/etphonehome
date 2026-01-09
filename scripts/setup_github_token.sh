#!/bin/bash
# Interactive setup for GitHub Personal Access Token

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  GitHub Personal Access Token Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This wizard will help you create and securely store a"
echo "GitHub Personal Access Token for ET Phone Home."
echo ""
echo "The token will be encrypted and stored locally with"
echo "machine-specific encryption."
echo ""

# Check if token already exists
if [ -f "$HOME/.etphonehome/github_token.enc" ]; then
    echo "⚠️  Existing token found at: $HOME/.etphonehome/github_token.enc"
    echo ""
    read -p "Do you want to replace it? [y/N]: " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 1: Create Personal Access Token"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Visit: https://github.com/settings/tokens/new"
echo ""
echo "2. Configure the token:"
echo "   • Note: ET Phone Home Secrets Management"
echo "   • Expiration: No expiration (or your preference)"
echo "   • Scopes: Check 'repo' (Full control of private repositories)"
echo ""
echo "3. Click 'Generate token'"
echo ""
echo "4. Copy the token (it starts with 'ghp_' or 'github_pat_')"
echo ""

read -p "Press Enter when you're ready to continue..."
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 2: Enter Your Token"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Paste your GitHub token below (input will be hidden):"
echo ""

# Read token securely (no echo)
read -s -p "Token: " GITHUB_TOKEN
echo ""
echo ""

# Validate token format
if [[ ! $GITHUB_TOKEN =~ ^(ghp_|github_pat_) ]]; then
    echo "❌ Invalid token format. Token should start with 'ghp_' or 'github_pat_'"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 3: Verify Token"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Verifying token..."

# Verify token by calling GitHub API
GITHUB_USER=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" https://api.github.com/user | python3 -c "import sys, json; print(json.load(sys.stdin).get('login', ''))" 2>/dev/null)

if [ -z "$GITHUB_USER" ]; then
    echo "❌ Token verification failed. Please check the token and try again."
    exit 1
fi

echo "✅ Token verified successfully!"
echo "👤 Authenticated as: $GITHUB_USER"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Step 4: Store Token Securely"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Encrypting and storing token..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Store token using Python script (run from project root)
cd "$PROJECT_ROOT"
python3 -c "
import sys
sys.path.insert(0, '.')
from shared.secrets_manager import SecureLocalStorage
storage = SecureLocalStorage()
storage.store_token('$GITHUB_TOKEN')
print('✅ Token stored successfully!')
print(f'   Location: {storage.storage_path}')
print(f'   Permissions: 0600 (owner read/write only)')
"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup Complete! ✅"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Your GitHub token is now securely stored and ready to use."
echo ""
echo "Next steps:"
echo "  1. Store R2 credentials in GitHub Secrets"
echo "  2. Test automatic key rotation"
echo ""
echo "For more information, see: docs/SECRETS_MANAGEMENT.md"
echo ""

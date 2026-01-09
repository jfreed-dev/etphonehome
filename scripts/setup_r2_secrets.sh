#!/bin/bash
# ET Phone Home - R2 Secrets Initial Setup Script
# This script guides you through setting up R2 credentials with GitHub Secrets
# and automatic rotation

set -e  # Exit on error

echo "============================================"
echo "ET Phone Home - R2 Secrets Setup"
echo "============================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Check if running from correct directory
if [ ! -f "pyproject.toml" ]; then
    print_error "Please run this script from the etphonehome root directory"
    exit 1
fi

echo "This script will guide you through:"
echo "  1. Creating a GitHub Personal Access Token"
echo "  2. Storing it securely locally"
echo "  3. Setting up initial R2 credentials in GitHub Secrets"
echo "  4. Configuring automatic key rotation"
echo ""

# Step 1: GitHub Token
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 1: GitHub Personal Access Token"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_info "You need a GitHub Personal Access Token (classic) with 'repo' scope"
echo ""
echo "To create one:"
echo "  1. Go to: https://github.com/settings/tokens"
echo "  2. Click 'Generate new token' → 'Generate new token (classic)'"
echo "  3. Give it a name: 'ET Phone Home Secrets Management'"
echo "  4. Select scopes: ✓ repo (full control of private repositories)"
echo "  5. Click 'Generate token'"
echo "  6. Copy the token (you won't see it again!)"
echo ""

read -sp "Paste your GitHub token: " GITHUB_TOKEN
echo ""

if [ -z "$GITHUB_TOKEN" ]; then
    print_error "GitHub token is required"
    exit 1
fi

# Store token securely
print_info "Storing GitHub token securely..."
python3 -m shared.secrets_manager store-token "$GITHUB_TOKEN"
print_success "GitHub token stored in ~/.etphonehome/github_token.enc (encrypted)"

# Step 2: GitHub Repository
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 2: GitHub Repository Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "Enter GitHub repository (owner/repo): " GITHUB_REPO

if [ -z "$GITHUB_REPO" ]; then
    print_error "GitHub repository is required"
    exit 1
fi

export ETPHONEHOME_GITHUB_REPO="$GITHUB_REPO"

# Test GitHub access
print_info "Testing GitHub access..."
if python3 -m shared.secrets_manager list --repo "$GITHUB_REPO" > /dev/null 2>&1; then
    print_success "GitHub access verified"
else
    print_error "Failed to access GitHub repository. Check token permissions."
    exit 1
fi

# Step 3: Cloudflare API Token
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 3: Cloudflare API Token"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_info "You need a Cloudflare API Token with R2 permissions"
echo ""
echo "To create one:"
echo "  1. Go to: https://dash.cloudflare.com/profile/api-tokens"
echo "  2. Click 'Create Token'"
echo "  3. Use 'Create Custom Token'"
echo "  4. Permissions:"
echo "     - Account > R2 > Edit"
echo "  5. Account Resources: Include > Specific account > [Your Account]"
echo "  6. Click 'Continue to summary' → 'Create Token'"
echo "  7. Copy the token"
echo ""

read -sp "Paste your Cloudflare API token: " CF_API_TOKEN
echo ""

if [ -z "$CF_API_TOKEN" ]; then
    print_error "Cloudflare API token is required"
    exit 1
fi

export ETPHONEHOME_CLOUDFLARE_API_TOKEN="$CF_API_TOKEN"

# Step 4: R2 Configuration
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 4: Cloudflare R2 Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_info "Enter your Cloudflare account ID (found in R2 dashboard URL)"
read -p "Account ID: " ACCOUNT_ID

if [ -z "$ACCOUNT_ID" ]; then
    print_error "Account ID is required"
    exit 1
fi

export ETPHONEHOME_R2_ACCOUNT_ID="$ACCOUNT_ID"

# Step 5: Initial R2 API Token (will be rotated)
echo ""
print_info "Now we'll use initial R2 credentials (for testing/dev)"
print_warning "These will be rotated immediately after setup"
echo ""
echo "Create a temporary R2 API token:"
echo "  1. Go to R2 dashboard: https://dash.cloudflare.com/r2"
echo "  2. Click 'Manage R2 API Tokens'"
echo "  3. Click 'Create API Token'"
echo "  4. Token name: 'etphonehome-initial' (will be deleted)"
echo "  5. Permissions: Object Read & Write"
echo "  6. Select bucket: [Your bucket]"
echo "  7. Click 'Create API Token'"
echo ""

read -p "R2 Access Key ID: " R2_ACCESS_KEY
read -sp "R2 Secret Access Key: " R2_SECRET_KEY
echo ""
read -p "R2 Bucket name: " R2_BUCKET
R2_REGION="${R2_REGION:-auto}"

if [ -z "$R2_ACCESS_KEY" ] || [ -z "$R2_SECRET_KEY" ] || [ -z "$R2_BUCKET" ]; then
    print_error "All R2 credentials are required"
    exit 1
fi

# Step 6: Store initial credentials in GitHub Secrets
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 6: Storing R2 Credentials in GitHub Secrets"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_info "Uploading initial credentials to GitHub Secrets..."

python3 -m shared.secrets_manager store-r2 \
    --repo "$GITHUB_REPO" \
    --account-id "$ACCOUNT_ID" \
    --access-key "$R2_ACCESS_KEY" \
    --secret-key "$R2_SECRET_KEY" \
    --bucket "$R2_BUCKET" \
    --region "$R2_REGION"

print_success "Initial R2 credentials stored in GitHub Secrets"

# Step 7: Immediate rotation
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 7: Initial Key Rotation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_info "Rotating to production keys..."
print_warning "The initial token ($R2_ACCESS_KEY) will be deleted"
echo ""

# Perform rotation
python3 -m shared.r2_rotation rotate --old-key "$R2_ACCESS_KEY"

print_success "R2 keys rotated successfully!"
print_info "New production keys are now stored in GitHub Secrets"

# Step 8: Save configuration
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Step 8: Saving Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create environment file
ENV_FILE="$HOME/.etphonehome/r2_config.env"
mkdir -p "$HOME/.etphonehome"

cat > "$ENV_FILE" << EOF
# ET Phone Home R2 Configuration
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

# GitHub Configuration
export ETPHONEHOME_GITHUB_REPO="$GITHUB_REPO"

# Cloudflare Configuration
export ETPHONEHOME_R2_ACCOUNT_ID="$ACCOUNT_ID"
export ETPHONEHOME_CLOUDFLARE_API_TOKEN="$CF_API_TOKEN"

# Note: R2 credentials are stored in GitHub Secrets and will be
# automatically injected by GitHub Actions. For local development,
# you can set them manually or retrieve from GitHub Secrets.
EOF

chmod 600 "$ENV_FILE"
print_success "Configuration saved to $ENV_FILE"

# Step 9: Setup complete
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Setup Complete! 🎉"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
print_success "R2 secrets management is now configured"
echo ""
echo "What was configured:"
echo "  ✓ GitHub token stored locally (encrypted)"
echo "  ✓ R2 credentials stored in GitHub Secrets"
echo "  ✓ Initial keys rotated to production keys"
echo "  ✓ Configuration saved"
echo ""
echo "Next steps:"
echo "  1. Source the configuration:"
echo "     source $ENV_FILE"
echo ""
echo "  2. Test R2 access:"
echo "     python3 -m shared.r2_client"
echo ""
echo "  3. Set up automatic rotation (add to crontab):"
echo "     # Rotate R2 keys every 90 days"
echo "     0 3 1 * * cd /path/to/etphonehome && source $ENV_FILE && python3 -m shared.r2_rotation auto"
echo ""
echo "  4. Manual rotation (if needed):"
echo "     python3 -m shared.r2_rotation rotate"
echo ""
echo "  5. Check rotation status:"
echo "     python3 -m shared.r2_rotation check"
echo ""
print_info "For more details, see docs/SECRETS_MANAGEMENT.md"

# Cleanup sensitive variables
unset GITHUB_TOKEN
unset CF_API_TOKEN
unset R2_SECRET_KEY

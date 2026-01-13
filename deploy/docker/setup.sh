#!/bin/bash
# =============================================================================
# ET Phone Home - Docker Production Setup Script
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}ET Phone Home - Docker Production Setup${NC}"
echo "========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${RED}Please edit .env with your configuration before continuing.${NC}"
    echo "Required settings:"
    echo "  - DOMAIN: Your domain name (e.g., etphonehome.example.com)"
    echo "  - ACME_EMAIL: Email for Let's Encrypt notifications"
    echo "  - CF_DNS_API_TOKEN: Cloudflare API token for DNS-01 challenge"
    echo ""
    exit 1
fi

# Source environment variables
source .env

# Validate required variables
missing_vars=()
[ -z "$DOMAIN" ] && missing_vars+=("DOMAIN")
[ -z "$ACME_EMAIL" ] && missing_vars+=("ACME_EMAIL")
[ -z "$CF_DNS_API_TOKEN" ] && missing_vars+=("CF_DNS_API_TOKEN")

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo -e "${RED}Missing required environment variables:${NC}"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo ""
    echo "Please edit .env and set these variables."
    exit 1
fi

echo -e "${GREEN}Environment variables validated${NC}"

# Generate API key if not set
if [ -z "$ETPHONEHOME_API_KEY" ] || [ "$ETPHONEHOME_API_KEY" = "your_api_key_here" ]; then  # pragma: allowlist secret
    echo "Generating API key..."
    NEW_API_KEY=$(openssl rand -hex 32)
    # Update the .env file with the generated key
    if grep -q "^ETPHONEHOME_API_KEY=" .env; then
        sed -i "s/^ETPHONEHOME_API_KEY=.*/ETPHONEHOME_API_KEY=$NEW_API_KEY/" .env
    else
        echo "ETPHONEHOME_API_KEY=$NEW_API_KEY" >> .env
    fi
    echo -e "${GREEN}API key generated and saved to .env${NC}"
    echo -e "${YELLOW}Save this key securely - you'll need it to access the API:${NC}"
    echo "$NEW_API_KEY"
    echo ""
    # Re-source to get the new key
    source .env
else
    echo "API key already configured"
fi

# Create acme.json for Let's Encrypt certificates
if [ ! -f traefik/acme.json ]; then
    echo "Creating acme.json for Let's Encrypt..."
    touch traefik/acme.json
    chmod 600 traefik/acme.json
    echo -e "${GREEN}Created traefik/acme.json${NC}"
else
    # Ensure correct permissions
    chmod 600 traefik/acme.json
fi

# Generate Traefik dashboard password
if [ -z "$TRAEFIK_DASHBOARD_AUTH" ]; then
    echo ""
    echo -e "${YELLOW}Traefik dashboard authentication not set.${NC}"
    read -p "Enter username for Traefik dashboard [admin]: " TRAEFIK_USER
    TRAEFIK_USER=${TRAEFIK_USER:-admin}
    read -s -p "Enter password for Traefik dashboard: " TRAEFIK_PASS
    echo ""

    if [ -n "$TRAEFIK_PASS" ]; then
        # Generate htpasswd entry (escape $ for docker-compose)
        HTPASSWD=$(htpasswd -nbB "$TRAEFIK_USER" "$TRAEFIK_PASS" | sed 's/\$/\$\$/g')
        echo "TRAEFIK_DASHBOARD_AUTH=$HTPASSWD" >> .env
        echo -e "${GREEN}Dashboard credentials added to .env${NC}"
    else
        echo -e "${RED}No password provided, skipping dashboard auth${NC}"
    fi
fi

# Validate Cloudflare token
echo ""
echo "Validating Cloudflare API token..."
CF_RESPONSE=$(curl -s -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
    -H "Authorization: Bearer $CF_DNS_API_TOKEN" \
    -H "Content-Type: application/json")

if echo "$CF_RESPONSE" | grep -q '"success":true'; then
    echo -e "${GREEN}Cloudflare API token is valid${NC}"
else
    echo -e "${RED}Cloudflare API token validation failed${NC}"
    echo "Response: $CF_RESPONSE"
    echo ""
    echo "Please check your CF_DNS_API_TOKEN in .env"
    exit 1
fi

# Build images
echo ""
echo "Building Docker images..."
docker compose -f docker-compose.prod.yml build

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Setup complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "To start the services:"
echo "  docker compose -f docker-compose.prod.yml up -d"
echo ""
echo "To view logs:"
echo "  docker compose -f docker-compose.prod.yml logs -f"
echo ""
echo "Your API key is stored in .env (ETPHONEHOME_API_KEY)"
echo ""
echo "Access your deployment at:"
echo "  https://$DOMAIN"
echo ""
echo "Traefik dashboard (if enabled):"
echo "  https://$DOMAIN/traefik"
echo ""

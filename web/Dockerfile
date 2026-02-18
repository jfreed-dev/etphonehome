# =============================================================================
# Reach - Frontend Dockerfile
# Multi-stage build for SvelteKit static site with nginx
# =============================================================================

# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies (ci for reproducible builds)
RUN npm ci

# Stage 2: Builder
FROM node:20-alpine AS builder
WORKDIR /app

# Copy dependencies from deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy source files
COPY . .

# Build the application
RUN npm run build

# Stage 3: Runtime (nginx for static files)
FROM nginx:alpine

# Install wget for health checks
RUN apk add --no-cache wget

# Create non-root user for nginx
RUN addgroup -g 1000 appuser && \
    adduser -u 1000 -G appuser -D appuser && \
    # Create required directories with correct ownership
    mkdir -p /var/cache/nginx /var/run/nginx /var/log/nginx && \
    chown -R appuser:appuser /var/cache/nginx /var/run/nginx /var/log/nginx && \
    # Allow nginx to bind to port 3000
    chown -R appuser:appuser /etc/nginx

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built static files
COPY --from=builder --chown=appuser:appuser /app/build /usr/share/nginx/html

# Switch to non-root user
USER appuser

# Expose port 3000 (non-privileged)
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:3000 || exit 1

# Start nginx in foreground
CMD ["nginx", "-g", "daemon off;"]

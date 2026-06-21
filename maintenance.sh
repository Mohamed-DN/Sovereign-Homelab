#!/usr/bin/env bash
# Sovereign Homelab - Maintenance and Update Script
# This script automates the safe update process for all stacks.

set -e

echo "Starting Sovereign Homelab Maintenance..."

# 1. ZFS Snapshot (if ZFS is available)
if command -v zfs &> /dev/null; then
    SNAP_NAME="maintenance-$(date +%F-%H%M)"
    echo "Creating ZFS snapshot: tank/apps@$SNAP_NAME"
    sudo zfs snapshot -r tank/apps@"$SNAP_NAME" || echo "Warning: ZFS snapshot failed or ZFS dataset tank/apps not found."
else
    echo "ZFS not detected, skipping snapshot."
fi

# 2. Update all Docker Compose stacks
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACKS_DIR="$BASE_DIR/stacks"

echo "Updating Docker containers..."
for dir in "$STACKS_DIR"/*/; do
    if [ -f "${dir}docker-compose.yml" ] || [ -f "${dir}docker-compose.yaml" ]; then
        STACK_NAME=$(basename "$dir")
        echo "========================================"
        echo "Updating stack: $STACK_NAME"
        cd "$dir"
        
        # Check if .env exists, if not warn
        if [ ! -f ".env" ] && [ -f ".env.example" ]; then
            echo "Warning: .env not found in $STACK_NAME! Skipping..."
            continue
        fi

        docker compose pull
        docker compose up -d --remove-orphans
    fi
done

# 3. Cleanup unused images
echo "========================================"
echo "Cleaning up dangling Docker images and volumes..."
docker image prune -af
docker volume prune -f

echo "Maintenance complete!"

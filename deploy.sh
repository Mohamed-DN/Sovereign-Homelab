#!/usr/bin/env bash
# Uniform deployment script

STACK="$1"

if [ -z "$STACK" ]; then
  echo "Usage: ./deploy.sh <stack_name>"
  echo "Available stacks:"
  ls -1 stacks/
  exit 1
fi

if [ ! -d "stacks/$STACK" ]; then
  echo "Error: Stack '$STACK' not found."
  exit 1
fi

echo "Deploying $STACK..."
cd "stacks/$STACK"

if [ -f "docker-compose.yml" ] || [ -f "docker-compose.yaml" ]; then
  docker compose pull
  docker compose up -d
  echo "Verifying health..."
  sleep 5
  docker compose ps
else
  echo "No docker-compose file found in stacks/$STACK"
  exit 1
fi

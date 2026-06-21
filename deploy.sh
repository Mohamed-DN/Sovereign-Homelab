#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ./deploy.sh <stack_name> [--pull]

Examples:
  ./deploy.sh vaultwarden
  ./deploy.sh observability --pull

Rules:
  - Run from the repository root.
  - Each stack must have stacks/<stack_name>/docker-compose.yml.
  - Each stack must have a real .env copied from .env.example.
  - This script validates Compose before starting containers.
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

STACK="$1"
PULL="${2:-}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_DIR="$ROOT_DIR/stacks/$STACK"
COMPOSE_FILE="$STACK_DIR/docker-compose.yml"
ENV_FILE="$STACK_DIR/.env"

if [[ ! -d "$STACK_DIR" ]]; then
  echo "ERROR: Stack '$STACK' does not exist under stacks/." >&2
  echo "Available stacks:" >&2
  find "$ROOT_DIR/stacks" -mindepth 1 -maxdepth 1 -type d -printf '  %f\n' | sort >&2
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: $COMPOSE_FILE is missing." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE is missing. Copy .env.example to .env and replace placeholders first." >&2
  exit 1
fi

cd "$STACK_DIR"

echo "Validating stack: $STACK"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet

if [[ "$PULL" == "--pull" ]]; then
  echo "Pulling images for stack: $STACK"
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull
elif [[ -n "$PULL" ]]; then
  echo "ERROR: Unknown option '$PULL'. Supported option: --pull" >&2
  exit 1
fi

echo "Starting stack: $STACK"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --remove-orphans

echo "Final state:"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps

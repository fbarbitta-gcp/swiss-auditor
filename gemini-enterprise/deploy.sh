#!/usr/bin/env bash
# deploy.sh - Bash-compatible alternative to `make deploy`
# Reads app/.env and passes all variables to the Vertex AI Agent Engine deployment.

set -euo pipefail

# Work from the script directory
cd "$(dirname "$0")"

ENV_FILE="app/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ Error: $ENV_FILE not found"
  exit 1
fi

echo "📦 Exporting dependencies..."
(uv export --no-hashes --no-header --no-dev --no-emit-project --no-annotate > app/app_utils/.requirements.txt 2>/dev/null || \
 uv export --no-hashes --no-header --no-dev --no-emit-project > app/app_utils/.requirements.txt)

echo "🌍 Reading environment variables from $ENV_FILE..."

# Exact variable names reserved by GCP or already injected by deploy.py.
RESERVED_EXACT=(
  "GOOGLE_CLOUD_PROJECT"   # Reserved by GCP platform
  "GOOGLE_CLOUD_REGION"    # Set by deploy.py from --location
  "GOOGLE_CLOUD_LOCATION"  # Extracted for deployment flag
  "NUM_WORKERS"            # Set by deploy.py from --num-workers
  "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT" # deploy.py default
)

# Variable name *prefixes* that are reserved by GCP (any variable starting
# with these strings will be rejected by the Vertex AI API).
RESERVED_PREFIXES=(
  "GOOGLE_CLOUD_AGENT_ENGINE"   # Entire prefix is reserved
)

is_reserved() {
  local key="$1"
  for exact in "${RESERVED_EXACT[@]}"; do
    [[ "$key" == "$exact" ]] && return 0
  done
  for prefix in "${RESERVED_PREFIXES[@]}"; do
    [[ "$key" == "${prefix}"* ]] && return 0
  done
  return 1
}

env_parts=()
PROJECT=""
LOCATION=""

while IFS= read -r line; do
  # Skip blank lines and comment lines
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

  # Normalize: trim spaces around '='
  # robust parsing: key is everything before first '='
  key="${line%%=*}"
  # value is everything after first '='
  value="${line#*=}"

  # Trim spaces
  key=$(echo "$key" | xargs)
  value=$(echo "$value" | sed "s/^[\"']\(.*\)[\"']$/\1/" | xargs)

  [[ -z "$key" ]] && continue

  # Extract deployment parameters
  if [[ "$key" == "GOOGLE_CLOUD_PROJECT" ]]; then
    PROJECT="$value"
  elif [[ "$key" == "GOOGLE_CLOUD_LOCATION" ]]; then
    LOCATION="$value"
  elif [[ "$key" == "GOOGLE_CLOUD_REGION" ]]; then
    LOCATION="$value"
  fi

  # Skip reserved / auto-injected variables from --set-env-vars
  if is_reserved "$key"; then
    echo "  ⚠️  Skipping reserved variable from env: $key"
    continue
  fi

  env_parts+=("${key}=${value}")
done < "$ENV_FILE"

# Join all parts with commas
ENV_VARS=$(IFS=','; echo "${env_parts[*]}")

echo "🌍 Passing ${#env_parts[@]} environment variables to deployment..."

DEPLOY_CMD=(uv run -m app.app_utils.deploy \
  --source-packages=./app \
  --entrypoint-module=app.agent_engine_app \
  --entrypoint-object=agent_engine \
  --requirements-file=app/app_utils/.requirements.txt)

if [[ -n "${PROJECT}" ]]; then
  DEPLOY_CMD+=(--project="$PROJECT")
fi

if [[ -n "${LOCATION}" ]]; then
  DEPLOY_CMD+=(--location="$LOCATION")
fi


if [[ -n "${ENV_VARS}" ]]; then
  DEPLOY_CMD+=(--set-env-vars="$ENV_VARS")
fi

# Forward any script arguments to deploy.py
DEPLOY_CMD+=("$@")

echo "🚀 Deploying to Vertex AI Agent Engine..."
"${DEPLOY_CMD[@]}"

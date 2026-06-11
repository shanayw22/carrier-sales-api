#!/usr/bin/env bash

set -euo pipefail

: "${ACCOUNT_ID:?Set ACCOUNT_ID}"
: "${AWS_REGION:?Set AWS_REGION}"
: "${DB_PASSWORD:?Set DB_PASSWORD}"
: "${RDS_ENDPOINT:?Set RDS_ENDPOINT}"
: "${APP_API_KEY:?Set APP_API_KEY}"
: "${FMCSA_API_KEY:?Set FMCSA_API_KEY}"

template_dir="$(cd "$(dirname "$0")" && pwd)"
template_file="$template_dir/task-definition.template.json"
output_file="$template_dir/task-definition.json"

envsubst < "$template_file" > "$output_file"
printf 'Wrote %s\n' "$output_file"
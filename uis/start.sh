#!/bin/sh
set -eu

cleanup() {
  kill "$website_pid" "$backoffice_pid" 2>/dev/null || true
  wait "$website_pid" "$backoffice_pid" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

cd /workspace/uis/website
npm run dev -- --hostname 0.0.0.0 --port 3000 &
website_pid=$!

cd /workspace/uis/backoffice
npm run dev -- --hostname 0.0.0.0 --port 3001 &
backoffice_pid=$!

wait -n "$website_pid" "$backoffice_pid"
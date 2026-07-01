#!/usr/bin/env bash
# Start the Marvis React frontend (:5173)
set -e
cd "$(dirname "$0")/frontend"
exec npm run dev

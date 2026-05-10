#!/usr/bin/env bash
# ------------------------------------------------------------
# run.sh — One-command startup for the Banking Transactions API
# Usage: ./demo/run.sh  (from inside homework-1/)
# ------------------------------------------------------------

set -e  # Stop immediately if any command fails

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "📦 Installing dependencies..."
cd "$PROJECT_DIR"
npm install

echo ""
echo "🚀 Starting the Banking Transactions API..."
echo ""
npm start

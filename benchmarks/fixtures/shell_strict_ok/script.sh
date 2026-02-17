#!/bin/bash
set -euo pipefail

# This script has strict mode enabled
echo "Deploying application"
cd /app
npm install --production
npm start

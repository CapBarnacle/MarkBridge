#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/.markbridge/logs"
LOG_FILE="${LOG_DIR}/markbridge-api.log"
PID_FILE="${LOG_DIR}/markbridge-api.pid"

mkdir -p "${LOG_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID="$(cat "${PID_FILE}")"
  if [[ -n "${OLD_PID}" ]] && kill -0 "${OLD_PID}" 2>/dev/null; then
    echo "MarkBridge API already running with PID ${OLD_PID}"
    echo "Log file: ${LOG_FILE}"
    exit 0
  fi
  rm -f "${PID_FILE}"
fi

cd "${ROOT_DIR}"
nohup env PYTHONPATH=src python3 -m uvicorn markbridge.api:app --host 0.0.0.0 --port 8000 >> "${LOG_FILE}" 2>&1 &
NEW_PID="$!"
echo "${NEW_PID}" > "${PID_FILE}"

echo "Started MarkBridge API"
echo "PID: ${NEW_PID}"
echo "Log file: ${LOG_FILE}"

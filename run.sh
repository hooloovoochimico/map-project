#!/usr/bin/env bash
# Esegue l'intera pipeline: fetch -> identify -> assign -> dissolve -> map
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3
export PYTHONUTF8=1

echo "## 1/5 fetch_data"
"$PY" src/fetch_data.py
echo "## 2/5 identify_capoluoghi"
"$PY" src/identify_capoluoghi.py
echo "## 3/5 assign"
"$PY" src/assign.py
echo "## 4/5 dissolve"
"$PY" src/dissolve.py
echo "## 5/5 make_map"
"$PY" src/make_map.py
echo
echo "Fatto. Apri outputs/map.html nel browser."

"""
JARVIS Main Entrypoint — Bridges to Production-Hardened dashboard_server
"""
import os
import sys

# Import everything from dashboard_server
import dashboard_server
from dashboard_server import app, ensure_engines_started

# Ensure worker fleet and sentinel are active
ensure_engines_started()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

#!/usr/bin/env python3
"""Serve la dashboard Lorcana su una porta HTTP accessibile."""
import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8050

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))

handler = http.server.SimpleHTTPRequestHandler
handler.extensions_map.update({".js": "application/javascript", ".json": "application/json"})

print(f"\n  Lorcana Dashboard: http://157.180.46.188:{PORT}/dashboard.html\n")
http.server.HTTPServer(("0.0.0.0", PORT), handler).serve_forever()

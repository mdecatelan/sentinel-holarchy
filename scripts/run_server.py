#!/usr/bin/env python3
"""
Sentinel-Holarchy: Integrated Web Dashboard & Telemetry API Gateway.
Provides REST endpoints (/api/telemetry, /api/state, /api/audit) and serves the HTML GUI.
"""

import sys
import os
import json
from http.server import SimpleHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from sentinel_holarchy.holon3_intelligence.simulator import DigitalTwinSimulator
from sentinel_holarchy.holon3_intelligence.openraman import OpenRamanPipeline
from sentinel_holarchy.holon2_workshop.ecocert_validator import EcocertUABAuditor, LabAssayResults

PORT = int(os.environ.get("PORT", 5000))
SIMULATOR = DigitalTwinSimulator(intrant_type="organique")
RAMAN = OpenRamanPipeline()
AUDITOR = EcocertUABAuditor()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class SentinelRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            dashboard_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard", "index.html"))
            if not os.path.exists(dashboard_path):
                dashboard_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Documentation", "sentinel_dashboard.html"))
            
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(dashboard_path, "rb") as f:
                self.wfile.write(f.read())
            return

        elif self.path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = SIMULATOR.get_telemetry()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif self.path == "/api/audit":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            assay = LabAssayResults()
            audit_res = AUDITOR.audit_batch(assay, "BATCH-LIVE")
            self.wfile.write(json.dumps(audit_res).encode("utf-8"))
            return

        super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        if self.path == "/api/telemetry":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            res = {"status": "ACK", "received_bytes": len(post_data)}
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        elif self.path == "/api/step":
            telemetry = SIMULATOR.step(dt_h=1.0)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(telemetry).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def main():
    print(f"[GATEWAY] Starting Sentinel-Holarchy Gateway on http://127.0.0.1:{PORT}")
    server = ThreadedHTTPServer(("0.0.0.0", PORT), SentinelRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[GATEWAY] Shutting down.")
        server.server_close()

if __name__ == "__main__":
    main()

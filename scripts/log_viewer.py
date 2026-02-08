#!/usr/bin/env python3
"""Simple log viewer server for project_inside_backend service logs.

Serves GET / and GET /logs (and /logs/) with journalctl output. For production
(e.g. https://www.se-ai.live:8888/logs) run this as a systemd service or under
supervisor so it stays up. Example: python3 scripts/log_viewer.py
"""
import subprocess
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import json

PORT = 8888
SERVICE_NAME = "project_inside_backend"

class LogHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)
        
        if path in ("/", "/logs"):
            # Get log lines (default 100)
            lines = int(query.get("lines", [100])[0])
            since = query.get("since", [None])[0]
            
            cmd = ["journalctl", "-u", SERVICE_NAME, "-n", str(lines), "--no-pager"]
            if since:
                cmd.extend(["--since", since])
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    logs = result.stdout or "(no log output)"
                else:
                    logs = f"journalctl failed (exit {result.returncode}). You may need to run this server with sudo or add the user to the 'systemd-journal' group.\nstderr: {result.stderr or 'none'}"
            except subprocess.TimeoutExpired:
                logs = "Error: journalctl timed out after 30s."
            except FileNotFoundError:
                logs = f"Error: journalctl not found. Is this a systemd system? Service name: {SERVICE_NAME}"
            except subprocess.CalledProcessError as e:
                logs = f"Error fetching logs: {e}\nstderr: {e.stderr or 'none'}"
            except Exception as e:
                logs = f"Error: {type(e).__name__}: {e}"
            
            # Return as HTML or JSON based on Accept header
            accept = self.headers.get("Accept", "")
            if "application/json" in accept:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"logs": logs}).encode())
            else:
                html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Backend Logs - {SERVICE_NAME}</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: monospace; margin: 20px; background: #1e1e1e; color: #d4d4d4; }}
        h1 {{ color: #4ec9b0; }}
        .controls {{ margin: 20px 0; }}
        input, button {{ padding: 8px; margin: 5px; background: #2d2d2d; color: #d4d4d4; border: 1px solid #555; }}
        button {{ cursor: pointer; }}
        button:hover {{ background: #3e3e3e; }}
        pre {{ background: #252526; padding: 15px; border-radius: 5px; overflow-x: auto; white-space: pre-wrap; }}
        .error {{ color: #f48771; }}
        .info {{ color: #4ec9b0; }}
    </style>
</head>
<body>
    <h1>Backend Logs: {SERVICE_NAME}</h1>
    <div class="controls">
        <form method="GET" action="/logs">
            <label>Lines:</label>
            <input type="number" name="lines" value="{lines}" min="10" max="1000">
            <label>Since (e.g., "10 minutes ago", "today"):</label>
            <input type="text" name="since" value="{since or ''}" placeholder="10 minutes ago">
            <button type="submit">Refresh</button>
            <button type="button" onclick="location.reload()">Reload</button>
        </form>
    </div>
    <pre>{self._escape_html(logs)}</pre>
    <script>
        // Auto-refresh every 5 seconds
        setTimeout(() => location.reload(), 5000);
    </script>
</body>
</html>"""
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(html.encode())
        
        elif path == "/status":
            try:
                result = subprocess.run(
                    ["systemctl", "status", SERVICE_NAME, "--no-pager"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                status = result.stdout
            except subprocess.CalledProcessError as e:
                status = f"Error: {e}\n{e.stderr}"
            
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(status.encode())
        
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
    
    def _escape_html(self, text):
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#x27;"))

    def log_message(self, format, *args):
        """Suppress default request logging so we don't flood journalctl."""
        pass

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), LogHandler) as httpd:
        print(f"Log viewer server running at http://0.0.0.0:{PORT}/")
        print(f"View logs: http://localhost:{PORT}/logs")
        print(f"Service status: http://localhost:{PORT}/status")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
            httpd.shutdown()

#!/usr/bin/env python3
import os
import sys
import json
import urllib.parse
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Add current dir to python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from validator_engine import InspectionValidatorEngine

PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, ".."))
RESOURCE_DIR = os.path.join(PROJECT_ROOT, "resource")
WEB_DIR = os.path.join(current_dir, "web")

engine = InspectionValidatorEngine(RESOURCE_DIR)

# App state
current_state = {
    "selected_mission_path": None,
    "selected_template_path": None,
    "mission_data": None,
    "template_data": None,
    "validation_result": None
}

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads for high performance."""
    daemon_threads = True

class ValidatorRequestHandler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_error_msg(self, message, status=400):
        self.send_json({"error": message}, status=status)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == '/api/missions':
            missions = engine.list_missions()
            self.send_json({"missions": missions})
            return

        elif path == '/api/templates':
            templates = engine.list_templates()
            self.send_json({"templates": templates})
            return

        elif path == '/api/current_state':
            self.send_json(current_state)
            return

        elif path == '/api/results':
            if not current_state["selected_mission_path"]:
                self.send_error_msg("No mission loaded yet.", 400)
                return
            try:
                m_data = engine.load_mission_data(current_state["selected_mission_path"])
                t_points = []
                if current_state["selected_template_path"]:
                    t_data = engine.load_template_data(current_state["selected_template_path"])
                    t_points = t_data.get("inspection_points", [])
                
                combined_results = engine.merge_missing_points(m_data["results"], t_points)
                summary_rep = engine.get_summary_report(m_data["results"], t_points)
                self.send_json({
                    "mission_folder": m_data["mission_folder"],
                    "csv_filename": m_data["csv_filename"],
                    "total_records": len(combined_results),
                    "results": combined_results,
                    "summary_report": summary_rep
                })
            except Exception as e:
                self.send_error_msg(str(e), 500)
            return

        elif path == '/api/media':
            rel_file_path = query.get('path', [None])[0]
            if not rel_file_path:
                self.send_error_msg("Missing file path query parameter", 400)
                return

            # Clean and sanitize file path
            rel_file_path = urllib.parse.unquote(rel_file_path)
            
            # Resolve full path safely within RESOURCE_DIR
            if os.path.isabs(rel_file_path):
                full_media_path = os.path.abspath(rel_file_path)
            else:
                full_media_path = os.path.abspath(os.path.join(RESOURCE_DIR, rel_file_path))

            if not full_media_path.startswith(RESOURCE_DIR) or not os.path.exists(full_media_path):
                self.send_error_msg(f"File not found: {rel_file_path}", 404)
                return

            self.serve_file_with_range(full_media_path)
            return

        # Serve Web UI Static Files
        if path == '/' or path == '/index.html':
            self.serve_static_file(os.path.join(WEB_DIR, 'index.html'))
        else:
            rel = path.lstrip('/')
            file_p = os.path.join(WEB_DIR, rel)
            if os.path.exists(file_p) and os.path.isfile(file_p):
                self.serve_static_file(file_p)
            else:
                self.send_error_msg("Not Found", 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b'{}'
        
        try:
            body = json.loads(post_body.decode('utf-8'))
        except Exception:
            body = {}

        if path == '/api/import':
            mission_folder = body.get('mission_folder')
            template_path = body.get('template_path')

            if not mission_folder or not template_path:
                self.send_error_msg("Both mission_folder and template_path are required.", 400)
                return

            # Resolve paths
            if not os.path.isabs(mission_folder):
                mission_folder = os.path.join(RESOURCE_DIR, mission_folder)
            if not os.path.isabs(template_path):
                template_path = os.path.join(RESOURCE_DIR, "path", template_path)

            try:
                m_data = engine.load_mission_data(mission_folder)
                t_data = engine.load_template_data(template_path)

                current_state["selected_mission_path"] = mission_folder
                current_state["selected_template_path"] = template_path
                current_state["mission_data"] = {
                    "folder_name": os.path.basename(mission_folder),
                    "csv_filename": m_data["csv_filename"],
                    "record_count": len(m_data["results"]),
                    "physical_files_count": len(m_data["physical_files"])
                }
                current_state["template_data"] = {
                    "filename": t_data["template_name"],
                    "total_waypoints": t_data["total_waypoints"],
                    "inspection_count": t_data["inspection_count"],
                    "via_count": t_data["via_count"]
                }
                current_state["validation_result"] = None

                self.send_json({
                    "status": "success",
                    "mission": current_state["mission_data"],
                    "template": current_state["template_data"]
                })
            except Exception as e:
                self.send_error_msg(f"Import failed: {str(e)}", 400)
            return

        elif path == '/api/validate':
            m_path = current_state["selected_mission_path"]
            t_path = current_state["selected_template_path"]

            if not m_path or not t_path:
                self.send_error_msg("Please import mission and template first.", 400)
                return

            try:
                val_res = engine.validate(m_path, t_path)
                current_state["validation_result"] = val_res
                self.send_json(val_res)
            except Exception as e:
                self.send_error_msg(f"Validation failed: {str(e)}", 500)
            return

        else:
            self.send_error_msg("Endpoint not found", 404)

    def serve_static_file(self, file_path):
        mime, _ = mimetypes.guess_type(file_path)
        if not mime:
            if file_path.endswith('.css'): mime = 'text/css'
            elif file_path.endswith('.js'): mime = 'application/javascript'
            else: mime = 'application/octet-stream'

        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', f'{mime}; charset=utf-8' if 'text' in mime else mime)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error_msg(f"Error reading file: {str(e)}", 500)

    def serve_file_with_range(self, file_path):
        file_size = os.path.getsize(file_path)
        mime, _ = mimetypes.guess_type(file_path)
        if not mime:
            if file_path.endswith('.mp4'): mime = 'video/mp4'
            elif file_path.endswith('.wav'): mime = 'audio/wav'
            elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'): mime = 'image/jpeg'
            elif file_path.endswith('.png'): mime = 'image/png'
            else: mime = 'application/octet-stream'

        range_header = self.headers.get('Range')

        if range_header:
            try:
                byte_range = range_header.strip().lower().replace('bytes=', '')
                start_str, end_str = byte_range.split('-')
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1
                if start >= file_size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{file_size}')
                    self.end_headers()
                    return
                end = min(end, file_size - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(length))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()

                try:
                    with open(file_path, 'rb') as f:
                        f.seek(start)
                        self.wfile.write(f.read(length))
                except (BrokenPipeError, ConnectionResetError):
                    pass
            except Exception:
                try:
                    self.send_response(400)
                    self.end_headers()
                except Exception:
                    pass
        else:
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            try:
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            except (BrokenPipeError, ConnectionResetError):
                pass

def run_server(port=8088):
    server_address = ('', port)
    httpd = ThreadedHTTPServer(server_address, ValidatorRequestHandler)
    print(f"==================================================")
    print(f" Robotics CAT Inspection Result Validator Server ")
    print(f" Running at: http://localhost:{port}")
    print(f" Resource dir: {RESOURCE_DIR}")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()

if __name__ == '__main__':
    port = 8088
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)

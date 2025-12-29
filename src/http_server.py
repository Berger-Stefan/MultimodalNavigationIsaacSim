
import threading
import json
import io
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import parse_qs, urlparse
from typing import Any
from src.bridge import SimBridge, direction_to_command

class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def start_debug_http_server_in_thread(
    bridge: SimBridge,
    *,
    host: str = "127.0.0.1",
    port: int = 8001,
) -> threading.Thread:
    """Expose a simple JSON endpoint for manual browser checks."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path or "/"
            query = parse_qs(parsed.query)

            if path in {"/", ""}:
                body = (
                    "SpotControl debug server\n\n"
                    "Endpoints:\n"
                    "  /state  - latest sim state as JSON\n"
                    "  /move?direction=forward&length=1.0  - send move command\n"
                    "  /stop   - stop immediately\n"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/state":
                payload = json.dumps(bridge.get_state()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if path == "/stop":
                bridge.set_base_command(0.0, 0.0, 0.0, 0.0)
                payload = json.dumps({"ok": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return

            if path == "/move":
                try:
                    direction = (query.get("direction") or [""])[0]
                    length = float((query.get("length") or ["0.2"])[0])
                    speed = float((query.get("speed") or ["1.0"])[0])
                    yaw_rate = float((query.get("yaw_rate") or ["0.8"])[0])
                    vx, vy, wz = direction_to_command(direction, speed, yaw_rate)
                    bridge.set_base_command(vx, vy, wz, length)
                    payload = json.dumps(
                        {
                            "ok": True,
                            "applied": {
                                "vx": vx,
                                "vy": vy,
                                "yaw_rate": wz,
                                "duration_s": length,
                            },
                        }
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                except Exception as exc:
                    payload = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

            if path == "/camera":
                try:
                    rgba = bridge.get_camera_rgba()
                    if rgba is None:
                        payload = json.dumps({"ok": False, "error": "No camera frame available"}).encode("utf-8")
                        self.send_response(503)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Content-Length", str(len(payload)))
                        self.end_headers()
                        self.wfile.write(payload)
                        return
                    
                    # Convert RGBA to PNG
                    try:
                        from PIL import Image
                        import numpy as np
                        arr = np.asarray(rgba, dtype=np.uint8)
                        img = Image.fromarray(arr, mode="RGBA")
                        png_buffer = io.BytesIO()
                        img.save(png_buffer, format="PNG")
                        png_data = png_buffer.getvalue()
                        
                        self.send_response(200)
                        self.send_header("Content-Type", "image/png")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(png_data)))
                        self.end_headers()
                        self.wfile.write(png_data)
                        return
                    except ImportError:
                        # Fallback: return raw RGBA as binary
                        import numpy as np
                        arr = np.asarray(rgba, dtype=np.uint8)
                        png_data = arr.tobytes()
                        
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("X-Image-Width", str(rgba.shape[1] if len(rgba.shape) > 1 else 512))
                        self.send_header("X-Image-Height", str(rgba.shape[0] if len(rgba.shape) > 0 else 512))
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(png_data)))
                        self.end_headers()
                        self.wfile.write(png_data)
                        return
                except Exception as exc:
                    payload = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    server = _ThreadingHTTPServer((host, int(port)), Handler)

    def _run() -> None:
        server.serve_forever(poll_interval=0.5)

    thread = threading.Thread(target=_run, name="debug-http-server", daemon=True)
    thread.start()
    return thread

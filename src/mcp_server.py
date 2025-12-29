
import threading
import io
from typing import Any, Dict
from src.bridge import SimBridge, direction_to_command

def create_mcp_server(bridge: SimBridge, *, name: str = "spot-control"):
    """Create a FastMCP server exposing tools that control/read the sim."""

    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "FastMCP is not available. Install the MCP Python SDK that provides "
            "`mcp.server.fastmcp.FastMCP` (often `pip install mcp`)."
        ) from exc

    mcp = FastMCP(name)

    @mcp.tool()
    def getState() -> Dict[str, Any]:
        """Return the most recently published sim state (pose, camera metadata, timestamps)."""
        return bridge.get_state()

    @mcp.tool()
    def giveMoveCommand(
        direction: str,
        length: float,
        speed: float = 0.5,
        yaw_rate: float = 0.8,
    ) -> Dict[str, Any]:
        """Move the robot in `direction` for `length` seconds."""

        vx, vy, wz = direction_to_command(direction, float(speed), float(yaw_rate))
        bridge.set_base_command(vx, vy, wz, float(length))
        return {
            "ok": True,
            "applied": {"vx": vx, "vy": vy, "yaw_rate": wz, "duration_s": float(length)},
        }

    @mcp.tool()
    def setBaseCommand(vx: float, vy: float, yaw_rate: float, duration: float = 0.2) -> Dict[str, Any]:
        """Set raw base command for a short duration."""

        bridge.set_base_command(float(vx), float(vy), float(yaw_rate), float(duration))
        return {"ok": True}

    @mcp.tool()
    def stop() -> Dict[str, Any]:
        """Immediately stop the robot."""

        bridge.set_base_command(0.0, 0.0, 0.0, 0.0)
        return {"ok": True}

    @mcp.tool()
    def getCameraImage() -> Dict[str, Any]:
        """Get the latest camera image as base64-encoded PNG."""
        import base64
        import numpy as np
        from PIL import Image
        
        try:
            rgba = bridge.get_camera_rgba()
            if rgba is None:
                return {"ok": False, "error": "No camera frame available"}
            
            arr = np.asarray(rgba, dtype=np.uint8)
            img = Image.fromarray(arr, mode="RGBA")
            png_buffer = io.BytesIO()
            img.save(png_buffer, format="PNG")
            png_data = png_buffer.getvalue()
            image_base64 = base64.b64encode(png_data).decode("utf-8")
            
            return {
                "ok": True,
                "image_base64": image_base64,
                "width": arr.shape[1] if len(arr.shape) > 1 else 512,
                "height": arr.shape[0] if len(arr.shape) > 0 else 512,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    def queryVisionModel(prompt: str, model: str = "qwen3-vl:4b") -> Dict[str, Any]:
        """Query the Ollama vision model with current camera image and a prompt.
        
        The model will analyze the camera view and respond based on the prompt.
        Common models: qwen3-vl:4b, llava:7b, etc.
        """
        import base64
        import numpy as np
        import requests
        from PIL import Image
        
        try:
            # Get camera image
            rgba = bridge.get_camera_rgba()
            if rgba is None:
                return {"ok": False, "error": "No camera frame available"}
            
            arr = np.asarray(rgba, dtype=np.uint8)
            img = Image.fromarray(arr, mode="RGBA")
            png_buffer = io.BytesIO()
            img.save(png_buffer, format="PNG")
            png_data = png_buffer.getvalue()
            image_base64 = base64.b64encode(png_data).decode("utf-8")
            
            # Query vision model
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": str(model),
                    "prompt": str(prompt),
                    "system": "You are a real-time robot vision system. Be extremely concise and fast. Do not be chatty. Output only the essential information requested.",
                    "images": [image_base64],
                    "stream": False,
                },
                timeout=60.0,
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "ok": True,
                    "response": result.get("response", "").strip(),
                    "model": model,
                }
            else:
                return {
                    "ok": False,
                    "error": f"Vision model returned status {response.status_code}: {response.text}",
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    return mcp


def start_mcp_server_in_thread(
    bridge: SimBridge,
    *,
    transport: str = "sse",
    host: str = "127.0.0.1",
    port: int = 8000,
    mount_path: str | None = None,
    name: str = "spot-control",
) -> threading.Thread:
    """Start FastMCP server in a daemon thread."""

    server = create_mcp_server(bridge, name=name)

    def _run() -> None:
        import os
        t = (transport or "").lower()
        if t == "sse":
            os.environ["MCP_SERVER_HOST"] = str(host)
            os.environ["MCP_SERVER_PORT"] = str(port)
            server.run(transport="sse", mount_path=mount_path)
        elif t in {"streamable-http", "streamable_http"}:
            server.run(transport="streamable-http")
        else:
            server.run(transport="stdio")

    thread = threading.Thread(target=_run, name="fastmcp-server", daemon=True)
    thread.start()
    return thread

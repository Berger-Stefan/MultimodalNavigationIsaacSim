from isaacsim import SimulationApp

# Initialize SimulationApp before other imports
simulation_app = SimulationApp({"headless": False})

import argparse
import carb
from src.bridge import SimBridge
from src.mcp_server import start_mcp_server_in_thread
from src.http_server import start_debug_http_server_in_thread
from src.simulation import SpotSimulation
from src.config import MCP_HOST, MCP_PORT, DEBUG_HTTP_PORT

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", default=False, action="store_true", help="Run in test mode")
    parser.add_argument("--mcp-disable", default=False, action="store_true", help="Disable MCP server")
    parser.add_argument("--mcp-host", default=MCP_HOST, help="FastMCP bind host (SSE transport)")
    parser.add_argument("--mcp-port", default=MCP_PORT, type=int, help="FastMCP bind port (SSE transport)")
    parser.add_argument(
        "--debug-http-port",
        default=DEBUG_HTTP_PORT,
        type=int,
        help="Port for debug HTTP server with /state, /move, /stop endpoints (0 to disable)",
    )
    args, unknown = parser.parse_known_args()

    bridge = SimBridge()

    if not args.mcp_disable:
        try:
            start_mcp_server_in_thread(bridge, host=args.mcp_host, port=args.mcp_port)
        except Exception as exc:
            try:
                carb.log_warn(f"MCP server failed to start: {exc}")
            except Exception:
                print(f"MCP server failed to start: {exc}")

    if args.debug_http_port and int(args.debug_http_port) > 0:
        try:
            start_debug_http_server_in_thread(bridge, host="127.0.0.1", port=int(args.debug_http_port))
        except Exception as exc:
            try:
                carb.log_warn(f"Debug HTTP server failed to start: {exc}")
            except Exception:
                print(f"Debug HTTP server failed to start: {exc}")

    # Start simulation
    sim = SpotSimulation(bridge, simulation_app)
    sim.run()

if __name__ == "__main__":
    main()

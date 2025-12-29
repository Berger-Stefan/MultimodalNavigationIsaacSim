
import os

# Network Configuration
MCP_HOST = "127.0.0.1"
MCP_PORT = 8000
DEBUG_HTTP_PORT = 8001

# Simulation Configuration
PHYSICS_DT = 1.0 / 500.0
RENDERING_DT = 1.0 / 50.0
STAGE_UNITS_IN_METERS = 1.0

# Robot Configuration
SPOT_INIT_POSITION = [0, 0, 0.8]
CAMERA_POSITION = [-0.5, 0.0, 0.8]
CAMERA_RESOLUTION = (512, 256)
CAMERA_FREQUENCY = 10
CAMERA_FOCAL_LENGTH = 1.0

# Environment Configuration
PALLET_ASSET_PATH = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Props/Pallet/o3dyn_pallet.usd"
DOME_LIGHT_INTENSITY = 1500.0

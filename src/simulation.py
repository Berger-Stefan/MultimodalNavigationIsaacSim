
import time
import carb
import numpy as np
from typing import Any, Dict, Optional

# Isaac Sim imports
from isaacsim.core.api import World
from isaacsim.sensors.camera import Camera
import isaacsim.core.utils.numpy.rotations as rot_utils
from isaacsim.core.utils.prims import define_prim
from isaacsim.robot.policy.examples.robots import SpotFlatTerrainPolicy
from isaacsim.storage.native import get_assets_root_path
from omni.isaac.core.utils.stage import add_reference_to_stage, get_current_stage
from omni.isaac.core.prims import XFormPrim
from pxr import UsdLux

from src.bridge import SimBridge
from src.config import (
    PHYSICS_DT, RENDERING_DT, STAGE_UNITS_IN_METERS,
    SPOT_INIT_POSITION, CAMERA_POSITION, CAMERA_RESOLUTION, CAMERA_FREQUENCY, CAMERA_FOCAL_LENGTH,
    PALLET_ASSET_PATH, DOME_LIGHT_INTENSITY
)

class SpotSimulation:
    def __init__(self, bridge: SimBridge, simulation_app):
        self.bridge = bridge
        self.simulation_app = simulation_app
        self.first_step = True
        self.reset_needed = False
        
        self.setup_world()
        self.setup_scene()
        self.setup_robot()
        
        self.world.reset()
        self.world.add_physics_callback("physics_step", callback_fn=self.on_physics_step)

    def setup_world(self):
        self.world = World(
            stage_units_in_meters=STAGE_UNITS_IN_METERS,
            physics_dt=PHYSICS_DT,
            rendering_dt=RENDERING_DT
        )
        assets_root_path = get_assets_root_path()
        if assets_root_path is None:
            carb.log_error("Could not find Isaac Sim assets folder")
            # Fallback or exit? For now just log.

        # spawn ground
        prim = define_prim("/World/Ground", "Xform")
        asset_path = assets_root_path + "/Isaac/Environments/Grid/default_environment.usd"
        prim.GetReferences().AddReference(asset_path)

    def setup_scene(self):
        # Add dome light
        stage = get_current_stage()
        dome_light = UsdLux.DomeLight.Define(stage, "/World/DomeLight")
        dome_light.GetIntensityAttr().Set(DOME_LIGHT_INTENSITY)
        dome_light.GetColorAttr().Set((1.0, 1.0, 1.0))

        # Add pallets
        self.add_pallet("pallet_01", [1.5, -1.5, 0.0])
        self.add_pallet("pallet_02", [1.5, 1.5, 0.0])
        self.add_pallet("pallet_03", [5.0, 0.0, 0.0])

    def add_pallet(self, name: str, position: list):
        prim_path = f"/World/{name}"
        add_reference_to_stage(usd_path=PALLET_ASSET_PATH, prim_path=prim_path)
        XFormPrim(
            prim_path=prim_path,
            name=name,
            position=position,
            orientation=[2, 0, 0, 0], # This orientation looks weird (not normalized quaternion?), keeping as is from original
        )

    def setup_robot(self):
        self.spot = SpotFlatTerrainPolicy(
            prim_path="/World/Spot",
            name="Spot",
            position=np.array(SPOT_INIT_POSITION),
        )
        self.camera = Camera(
            prim_path="/World/Spot/body/Camera",
            position=np.array(CAMERA_POSITION),
            frequency=CAMERA_FREQUENCY,
            resolution=CAMERA_RESOLUTION,
            orientation=rot_utils.euler_angles_to_quats(np.array([0, 0, 0]), degrees=True),
        )
        self.camera.set_focal_length(CAMERA_FOCAL_LENGTH)
        
        try:
            self.world.scene.add(self.camera)
        except Exception:
            pass

    def on_physics_step(self, step_size) -> None:
        if self.first_step:
            self.spot.initialize()
            try:
                self.camera.initialize()
            except Exception:
                pass
            self.first_step = False
        elif self.reset_needed:
            self.world.reset(True)
            self.reset_needed = False
            self.first_step = True
        else:
            vx, vy, wz = self.bridge.get_base_command()
            cmd = np.array([vx, vy, wz], dtype=float)
            self.spot.forward(step_size, cmd)

    def _safe_get_spot_pose(self) -> dict:
        try:
            pos, quat = self.spot.get_world_pose()
            euler = rot_utils.quat_to_euler_angles(quat)
            return {
                "position": [float(pos[0]), float(pos[1]), float(pos[2])],
                "orientation_xyzw": [float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])],
                "orientation_euler_rad": [float(euler[0]), float(euler[1]), float(euler[2])],
                "orientation_yaw_rad": float(euler[2]),
            }
        except Exception:
            return {}

    def _safe_get_camera_summary(self) -> dict:
        summary: Dict[str, Any] = {"resolution": list(CAMERA_RESOLUTION)}
        try:
            rgba = self.camera.get_rgba()
            if rgba is None:
                return summary
            arr = np.asarray(rgba)
            if arr.size == 0:
                return summary
            mean = arr.reshape(-1, arr.shape[-1]).mean(axis=0)
            summary["rgba_mean"] = [float(x) for x in mean]
            summary["has_frame"] = True
            return summary
        except Exception:
            summary["has_frame"] = False
            return summary

    def run(self):
        while self.simulation_app.is_running():
            self.world.step(render=True)
            if self.world.is_stopped():
                self.reset_needed = True
            if self.world.is_playing(): 
                vx, vy, wz = self.bridge.get_base_command()
                try:
                    camera_rgba = self.camera.get_rgba()
                    self.bridge.set_camera_rgba(camera_rgba)
                except Exception:
                    pass
                self.bridge.update_state(
                    {
                        "timestamp": time.time(),
                        "spot": self._safe_get_spot_pose(),
                        "base_command": {"vx": vx, "vy": vy, "yaw_rate": wz},
                        "camera": self._safe_get_camera_summary(),
                    }
                )
        
        self.simulation_app.close()

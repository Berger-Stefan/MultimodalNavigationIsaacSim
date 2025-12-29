
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple, Optional

@dataclass
class SimBridge:
    """Thread-safe shared state between Isaac Sim loop and MCP tools."""

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _last_state: Dict[str, Any] = field(default_factory=dict, init=False)
    _camera_rgba: Optional[Any] = field(default=None, init=False)

    # Base command is (vx [m/s], vy [m/s], yaw_rate [rad/s]).
    _base_command: Tuple[float, float, float] = field(default=(0.0, 0.0, 0.0), init=False)
    _command_until_walltime: float = field(default=0.0, init=False)

    def set_base_command(self, vx: float, vy: float, yaw_rate: float, duration_s: float) -> None:
        duration_s = max(0.0, float(duration_s))
        until = time.time() + duration_s
        with self._lock:
            self._base_command = (float(vx), float(vy), float(yaw_rate))
            self._command_until_walltime = until

    def get_base_command(self) -> Tuple[float, float, float]:
        now = time.time()
        with self._lock:
            if now > self._command_until_walltime:
                return (0.0, 0.0, 0.0)
            return self._base_command

    def update_state(self, state: Dict[str, Any]) -> None:
        with self._lock:
            self._last_state = dict(state)

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._last_state)

    def set_camera_rgba(self, rgba: Any) -> None:
        with self._lock:
            self._camera_rgba = rgba

    def get_camera_rgba(self) -> Optional[Any]:
        with self._lock:
            return self._camera_rgba


def direction_to_command(direction: str, speed: float, yaw_rate: float) -> Tuple[float, float, float]:
    d = (direction or "").strip().lower()
    if d in {"forward", "fwd", "front"}:
        return (speed, 0.0, 0.0)
    if d in {"back", "backward", "reverse"}:
        return (-speed, 0.0, 0.0)
    if d in {"left", "strafe_left"}:
        return (0.0, speed, 0.0)
    if d in {"right", "strafe_right"}:
        return (0.0, -speed, 0.0)
    if d in {"turn_left", "yaw_left", "rotate_left"}:
        return (0.0, 0.0, yaw_rate)
    if d in {"turn_right", "yaw_right", "rotate_right"}:
        return (0.0, 0.0, -yaw_rate)
    if d in {"stop", "halt"}:
        return (0.0, 0.0, 0.0)
    raise ValueError(
        "Unknown direction. Use one of: forward/back/left/right/turn_left/turn_right/stop"
    )

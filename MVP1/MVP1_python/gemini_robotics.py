import time
import asyncio
import numpy as np
import carb

from isaacsim.sensors.camera import Camera
from omni.isaac.core import PhysicsContext
import omni.physx

class CameraStream:
    """
    Stream RGB frames from an existing Camera prim using Isaac Sim's Camera wrapper.
    No Replicator, no networking.
    """

    def __init__(self, camera_prim_path: str, on_frame_cb=None, fps: float = 10.0, resolution=(640, 480)):
        self.camera_prim_path = camera_prim_path
        self.on_frame_cb = on_frame_cb
        self.fps = float(fps)
        self.resolution = tuple(resolution)

        self._camera = None
        self._physics_sub = None
        self._running = False
        self._last_call = 0.0

    async def initialize(self):
        # Attach to an *existing* camera prim
        self._camera = Camera(
            prim_path=self.camera_prim_path,
            frequency=max(1.0, self.fps),
            resolution=self.resolution,
        )
        self._camera.initialize()

        carb.log_info(f"✅ CameraStream initialized: {self.camera_prim_path} @ {self.resolution}")

    def start(self):
        if self._running:
            return
        if self._camera is None:
            raise RuntimeError("CameraStream.start() called before initialize()")

        self._running = True
        self._physics_sub = omni.physx.get_physx_interface().subscribe_physics_step_events(
            self._on_physics_step
        )

        carb.log_info("▶ CameraStream started")


    def stop(self):
        self._running = False

        if self._physics_sub:
            self._physics_sub.unsubscribe()
            self._physics_sub = None

        carb.log_info("⏹ CameraStream stopped")


    def _on_physics_step(self, dt: float):
        if not self._running:
            return

        now = time.time()
        if self.fps > 0 and (now - self._last_call) < (1.0 / self.fps):
            return

        self._last_call = now
        asyncio.ensure_future(self._capture_frame())

    async def _capture_frame(self):
        try:
            # get_rgba() returns float or uint depending on config; normalize to uint8 RGB
            rgba = self._camera.get_rgba()
            if rgba is None:
                return

            # handle float [0..1] or uint8 [0..255]
            if rgba.dtype != np.uint8:
                rgba = np.clip(rgba * 255.0, 0, 255).astype(np.uint8)

            rgb = rgba[:, :, :3]  # drop alpha

            if self.on_frame_cb:
                self.on_frame_cb(rgb)

        except Exception as e:
            carb.log_warn(f"CameraStream capture error: {e}")

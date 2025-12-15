import numpy as np
from pathlib import Path
from omni.isaac.core import World
from omni.isaac.core.objects import DynamicCuboid, VisualSphere, GroundPlane
from isaacsim.core.prims import SingleArticulation, SingleXFormPrim, XFormPrim
from isaacsim.core.utils.stage import add_reference_to_stage, get_current_stage
from isaacsim.storage.native import get_assets_root_path
from pxr import UsdGeom, UsdLux
import re
from omni.isaac.sensor import Camera
from omni.isaac.core.utils.rotations import euler_angles_to_quat
import time
from omni.isaac.core.utils.prims import is_prim_path_valid
from omni.isaac.core.utils import rotations as rot_utils

class Spawner:
    ASSETS_ROOT = get_assets_root_path()

    ASSET_LIBRARY = {
        "kitchen": f"{ASSETS_ROOT}/Isaac/IsaacLab/Arena/assets/background_library/"
                "kitchen_scene_teleop_v3/kitchen_scene_teleop_closed_drawer.usd",

        "office": f"{ASSETS_ROOT}/Isaac/Environments/Office/office.usd",
        "room": f"{ASSETS_ROOT}/Isaac/Environments/Simple_Room/simple_room.usd",
        "warehouse": f"{ASSETS_ROOT}/Isaac/Environments/Simple_Warehouse/warehouse.usd",

        "packing table": f"{ASSETS_ROOT}/Isaac/Props/PackingTable/packing_table.usd",

        "unitree": f"{ASSETS_ROOT}/Isaac/Robots/Unitree/H1/payloads/base.usda",
    }


    def __init__(self):
        self._spawned_prims = set()

    def _world(self):
        world = World.instance()
        return world if world else World()

    def _ensure_environment(self):
        """
        Spawns a ground plane and a light ONCE.
        These are persistent and should not be deleted on reset.
        """
        stage = get_current_stage()
        world = self._world()

        # --------------------------------------------------
        # Environment root
        # --------------------------------------------------
        if not stage.GetPrimAtPath("/World/Environment"):
            UsdGeom.Xform.Define(stage, "/World/Environment")

        # --------------------------------------------------
        # Ground plane
        # --------------------------------------------------
        if not stage.GetPrimAtPath("/World/Environment/GroundPlane"):
            ground = GroundPlane(
                prim_path="/World/Environment/GroundPlane",
                size=50.0,
                color=np.array([0.5, 0.5, 0.5]),
            )
            if not world.scene.get_object("ground_plane"):
                world.scene.add(ground)

        # --------------------------------------------------
        # Light
        # --------------------------------------------------
        if not stage.GetPrimAtPath("/World/Environment/Light"):
            light_prim = UsdLux.DistantLight.Define(
                stage, "/World/Environment/Light"
            )
            light_prim.CreateIntensityAttr(3000.0)
            light_prim.CreateAngleAttr(0.5)


    def _ensure_chat_root(self):
        stage = get_current_stage()
        if not stage.GetPrimAtPath("/World/Chat"):
            UsdGeom.Xform.Define(stage, "/World/Chat")
    # --------------------------------------------------
    # RESET (FIXED)
    # --------------------------------------------------
    def reset_environment(self):
        stage = get_current_stage()

        root = stage.GetPrimAtPath("/World/Chat")
        if root:
            stage.RemovePrim("/World/Chat")

        self._spawned_prims.clear()
        return "Environment reset."

    
    def _next_index(self, prefix: str) -> int:
        """
        Finds the next available index for prims like:
        /World/Chat/Unitree_0
        /World/Chat/Unitree_1
        """
        stage = get_current_stage()
        pattern = re.compile(rf"{prefix}_(\d+)$")

        max_idx = -1
        for prim in stage.Traverse():
            name = prim.GetName()
            match = pattern.match(name)
            if match:
                max_idx = max(max_idx, int(match.group(1)))

        return max_idx + 1

    # --------------------------------------------------
    # BASIC SHAPES
    # --------------------------------------------------
    def spawn_cube_at(self, pos):
        self._prepare_spawn()
        world = self._world()

        prim = f"/World/Chat/Cube_{len(self._spawned_prims)}"
        cube = DynamicCuboid(
            prim_path=prim,
            position=np.array(pos),
            size=0.1,
        )
        world.scene.add(cube)

        self._spawned_prims.add(prim)
        return f"Cube spawned at {pos}"


    def spawn_sphere_at(self, pos):
        self._prepare_spawn()
        world = self._world()

        prim = f"/World/Chat/Sphere_{len(self._spawned_prims)}"
        sphere = VisualSphere(
            prim_path=prim,
            position=np.array(pos),
            radius=0.1,
        )
        world.scene.add(sphere)

        self._spawned_prims.add(prim)
        return f"Sphere spawned at {pos}"

    # --------------------------------------------------
    # ROBOT HEAD CAMERA
    # --------------------------------------------------
    def attach_head_camera(self, robot_prim_path):
        camera_prim = f"{robot_prim_path}/d435_rgb_module_link/head_camera"

        # Use degrees=True to avoid mistakes
        orientation = rot_utils.euler_angles_to_quat(
            np.array([90, 90, 0]), degrees=True  # Adjust based on desired facing
        )

        # Set a reasonable position relative to the link
        position = np.array([2.2822972338678706, -0.5025799814929452, 1.5654207644517726])  # Relative offset (update as needed)

        cam = Camera(
            prim_path=camera_prim,
            position=position,
            orientation=orientation,
            resolution=(640, 480),
            frequency=30,
        )

        cam.initialize()
        self._head_camera = cam

        return camera_prim

    
    # --------------------------------------------------
    # ROBOT (ONLY articulation in system)
    # --------------------------------------------------
    def spawn_unitree_at(self, pos=None):
        self._prepare_spawn()

        if pos is None:
            pos = [2.6, -0.4, 1.1]

        idx = self._next_index("Unitree")
        prim_path = f"/World/Chat/Unitree_{idx}"

        # Load robot asset
        add_reference_to_stage(self.ASSET_LIBRARY["unitree"], prim_path)

        # Wait for prim to become valid
        timeout = 3.0
        elapsed = 0.0
        while not is_prim_path_valid(prim_path):
            time.sleep(0.1)
            elapsed += 0.1
            if elapsed >= timeout:
                raise RuntimeError(f"Timeout waiting for robot at {prim_path}")

        # Create articulation
        robot = SingleArticulation(prim_path)
        robot.set_world_pose(
            position=np.array(pos),
            orientation=[0, 0, 0, 1]
        )

        # ✅ No scene.add() needed
        self._spawned_prims.add(prim_path)

        # ✅ Attach camera
        cam_prim = self.attach_head_camera(prim_path)

        return f"Unitree spawned with head camera ({cam_prim})"


    # --------------------------------------------------
    # SCENES (NO articulation, NO physics add)
    # --------------------------------------------------
    def spawn_scene(self, name):
        self._ensure_chat_root()
        stage = get_current_stage()

        for k, usd in self.ASSET_LIBRARY.items():
            if k in name:
                prim = f"/World/Chat/Scene_{k}"
                if stage.GetPrimAtPath(prim):
                    return f"{k} scene already loaded."

                add_reference_to_stage(str(usd), prim)
                self._spawned_prims.add(prim)
                return f"{k} scene loaded."

        return f"Unknown scene: {name}"

    def _prepare_spawn(self):
        self._ensure_environment()
        self._ensure_chat_root()
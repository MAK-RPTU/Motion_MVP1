# spawner.py

import re
import numpy as np

from omni.isaac.core import World
from omni.isaac.core.objects import DynamicCuboid, VisualSphere
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.stage import add_reference_to_stage
from isaacsim.storage.native import get_assets_root_path


class Spawner:

    def _extract_position(self, text: str):
        match = re.search(r"\((.*?)\)", text)
        if not match:
            return np.array([0.0, 0.0, 0.0])
        values = match.group(1).split(",")
        return np.array([float(v) for v in values])

    # def _ensure_world(self):
    #     try:
    #         return World.instance()
    #     except Exception:
    #         print("[Spawner] No world exists; creating new World()")
    #         return World()
    
    def _ensure_world(self):
        world = World.instance()
        if world is None:
            print("[Spawner] No world exists; creating new World()")
            world = World()
        return world


    # -----------------------------------------------------

    # In spawner.py

    def spawn_cube_at(self, pos):
        world = self._ensure_world()
        cube = DynamicCuboid(
            prim_path=f"/World/ChatCube_{np.random.randint(1000)}",
            name="ChatCube",
            position=np.array(pos),
            size=0.1,
        )
        world.scene.add(cube)
        return f"Cube spawned at {tuple(pos)}."

    def spawn_sphere_at(self, pos):
        world = self._ensure_world()
        sphere = VisualSphere(
            prim_path=f"/World/ChatSphere_{np.random.randint(1000)}",
            name="ChatSphere",
            radius=0.1,
            position=np.array(pos),
        )
        world.scene.add(sphere)
        return f"Sphere spawned at {tuple(pos)}."

    def spawn_franka_at(self, pos):
        world = self._ensure_world()
        prim_path = f"/World/Unitree_{np.random.randint(1000)}"
        usd_path = (
            get_assets_root_path()
            # + "/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd"
            + "/Isaac/Robots/Unitree/H1/payloads/base.usda"
        )
        add_reference_to_stage(usd_path, prim_path)
        robot = SingleArticulation(prim_path)
        robot.set_world_pose(pos, [0, 0, 0, 1])
        world.scene.add(robot)
        return f"Franka spawned at {tuple(pos)}."


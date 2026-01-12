import numpy as np
from pathlib import Path
from omni.isaac.core import World
from omni.isaac.core.objects import DynamicCuboid, VisualSphere, GroundPlane
from isaacsim.core.prims import SingleArticulation, SingleXFormPrim, XFormPrim
from isaacsim.core.utils.stage import add_reference_to_stage, get_current_stage
from isaacsim.storage.native import get_assets_root_path
from pxr import Usd, UsdGeom, UsdLux, UsdPhysics, PhysxSchema
import re
from omni.isaac.sensor import Camera
from omni.isaac.core.utils.rotations import euler_angles_to_quat
import time
from omni.isaac.core.utils.prims import is_prim_path_valid
from omni.isaac.core.utils import rotations as rot_utils
import omni.kit.app
import omni.timeline
import omni.kit.commands
import omni.physx as _physx
import omni.kit.async_engine as async_engine 

import asyncio
import random
import omni.client
import os
import json

NUCLEUS_CACHE_FILE = "/home/ubuntu/.cache/nucleus_asset_index.json"

class Spawner:
    HAS_CONTENT = 0x1  # omniverse internal flag
    ASSETS_ROOT = get_assets_root_path()

    ASSET_LIBRARY = {
        "kitchen": f"{ASSETS_ROOT}/Isaac/IsaacLab/Arena/assets/background_library/kitchen_scene_teleop_v3/kitchen_scene_teleop_closed_drawer.usd",

        "office": f"{ASSETS_ROOT}/Isaac/Environments/Office/office.usd",
        "room": f"{ASSETS_ROOT}/Isaac/Environments/Simple_Room/simple_room.usd",
        "warehouse": f"{ASSETS_ROOT}/Isaac/Environments/Simple_Warehouse/warehouse.usd",

        "warehouse_breadcrates": f"/home/ubuntu/Motion_MVP1/Sample_scenes_Unitreeh1/Warehouse_Brot.usd",

        "packing table": f"{ASSETS_ROOT}/Isaac/Props/PackingTable/packing_table.usd",

        "unitree": f"{ASSETS_ROOT}/Isaac/Robots/Unitree/H1/payloads/base.usda",

        "yellow mug": f"{ASSETS_ROOT}/Isaac/Props/Mugs/SM_Mug_C1.usd",

        "black mug": f"{ASSETS_ROOT}/Isaac/Props/Mugs/SM_Mug_B1.usd",
    }

    SCENE_LIBRARY = {
        "kitchen": ASSET_LIBRARY["kitchen"],
        "office": ASSET_LIBRARY["office"],
        "room": ASSET_LIBRARY["room"],
        "warehouse": ASSET_LIBRARY["warehouse"],
        "warehouse_breadcrates": ASSET_LIBRARY["warehouse_breadcrates"],
        }
    
    SCENE_ALIASES = {
        "warehouse_breadcrates": [
            "warehouse with bread",
            "bread warehouse",
            "bread factory",
            "factory with bread",
            "bread storage",
            "bread crates warehouse",
        ],
        "warehouse": [
            "factory",
            "industrial hall",
            "storage hall",
        ],
    }


    def __init__(self):
        self._spawned_prims = set()

        # --- Full Nucleus ---
        self.NUCLEUS_ROOTS = [
            "omniverse://35.227.93.135/NVIDIA/Assets",
            "omniverse://35.227.93.135/NVIDIA/Environments",
        ]


        # Nucleus Test Roots to cache
        # self.NUCLEUS_ROOTS = [
        #     "omniverse://35.227.93.135/NVIDIA/Assets/Isaac/5.1/Isaac/Props/Mugs",
        #     "omniverse://35.227.93.135/NVIDIA/Assets/ArchVis/Residential/Decor/Books",
        # ]

        self._nucleus_index = None

        self.SEMANTIC_LOCATIONS = {
            "sink": {
                "x_min": 1.787636306238167,
                "x_max": 2.277535611777558,
                "y_min": 0.017787016541670947,
                "y_max": 0.37693285459455794,
                "z": 0.7841508388519287,
            }
        }


        self.DEFAULT_ASSET_POSITION = [1.756650568756057, 0.0, 1.0909934857926475]


        DEFAULT_ASSET_AREA = {
            # "x_min": 2.5758770259863537,
            # "x_max": 3.0930301090347485,
            # "y_min": 0.17586957972383563,
            # "y_max": 0.4928272805675453,
            # "z": 1.0909935235977168,

            "x_min": 2.42951,
            "x_max": 3.92451,
            "y_min": 0.10206,
            "y_max": 0.46199,
            "z": 0.957,
        }
        self.DEFAULT_ASSET_AREA = DEFAULT_ASSET_AREA

        if os.path.exists(NUCLEUS_CACHE_FILE):
            try:
                with open(NUCLEUS_CACHE_FILE, "r") as f:
                    self._nucleus_index = json.load(f)
                print(f"[Spawner] Loaded Nucleus index from cache ({len(self._nucleus_index)} assets)")
            except Exception as e:
                print("[Spawner] Failed to load cache:", e)

    async def _next_frames(self, n=2):
        for _ in range(max(1, int(n))):
            await self._app.next_update_async()

    # -------------------------------
    # HARD SCENE REMOVE (FIX)
    # -------------------------------
    async def remove_scene_clean_async(self, scene_name: str) -> str:
        stage = get_current_stage()
        app = omni.kit.app.get_app()
        timeline = omni.timeline.get_timeline_interface()

        scene_path = f"/World/Chat/Scene_{scene_name}"
        root = stage.GetPrimAtPath(scene_path)

        if not root or not root.IsValid():
            return f"No scene '{scene_name}' found."

        # 1️⃣ Stop simulation (pause is NOT enough for heavy PhysX scenes)
        try:
            timeline.stop()
        except Exception:
            pass

        # 2️⃣ Let PhysX + USD settle
        await app.next_update_async()
        await app.next_update_async()

        # 3️⃣ Delete via Kit command (stronger than RemovePrim)
        try:
            omni.kit.commands.execute(
                "DeletePrims",
                paths=[scene_path]
            )
        except Exception:
            stage.RemovePrim(scene_path)

        # 4️⃣ Flush updates
        await app.next_update_async()
        await app.next_update_async()

        return f"Scene '{scene_name}' removed cleanly."


    def _collect_subtree_paths(self, root_prim):
        # children first (deepest-first) so physics objects detach cleanly
        paths = []
        for p in Usd.PrimRange(root_prim):
            paths.append(p.GetPath().pathString)
        paths.sort(key=lambda s: s.count("/"), reverse=True)
        return paths
    
    def _break_composition(self, prim):
        # Unload payloads (important for heavy scenes)
        try:
            if prim.HasPayload():
                prim.Unload()
        except Exception:
            pass

        # Clear explicit references/payloads (helps detach composed content)
        try:
            prim.GetReferences().ClearReferences()
        except Exception:
            pass

        try:
            prim.GetPayloads().ClearPayloads()
        except Exception:
            pass

    def _disable_physics_apis(self, prim):
        # Disable rigid bodies
        try:
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                rb = UsdPhysics.RigidBodyAPI(prim)
                if rb:
                    en = rb.GetRigidBodyEnabledAttr()
                    if en:
                        en.Set(False)
        except Exception:
            pass

        # Disable collisions
        try:
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                col = UsdPhysics.CollisionAPI(prim)
                if col:
                    en = col.GetCollisionEnabledAttr()
                    if en:
                        en.Set(False)
        except Exception:
            pass

        # PhysX-specific (if present)
        try:
            if prim.HasAPI(PhysxSchema.PhysxRigidBodyAPI):
                prb = PhysxSchema.PhysxRigidBodyAPI(prim)
                # some versions expose enabled attr differently; best-effort
                attr = prim.GetAttribute("physxRigidBody:enabled")
                if attr:
                    attr.Set(False)
        except Exception:
            pass


    async def build_nucleus_index_async(self):
        if self._nucleus_index is not None:
            return self._nucleus_index

        print("[Spawner] Async indexing Nucleus assets...")

        assets = []

        async def crawl(root_url):
            result, entries = await omni.client.list_async(root_url)
            if result != omni.client.Result.OK:
                return

            for e in entries:
                full_path = f"{root_url}/{e.relative_path}"
                is_file = bool(e.flags & self.HAS_CONTENT)

                if any(x in full_path.lower() for x in ["/.thumbs", "/textures"]):
                    continue

                if is_file:
                    if full_path.lower().endswith((".usd", ".usda", ".usdc")):
                        assets.append(full_path)
                else:
                    await crawl(full_path)

        for root in self.NUCLEUS_ROOTS:
            await crawl(root)

        index = []
        for p in assets:
            text = (
                p.lower()
                .replace("omniverse://", "")
                .replace("/", " ")
                .replace("_", " ")
            )
            index.append({"path": p, "text": text})

        self._nucleus_index = index
        print(f"[Spawner] Indexed {len(index)} USD assets (async)")

        try:
            os.makedirs(os.path.dirname(NUCLEUS_CACHE_FILE), exist_ok=True)
            with open(NUCLEUS_CACHE_FILE, "w") as f:
                # json.dump(index, f)
                json.dump(index, f, indent=2, ensure_ascii=False)
            print("[Spawner] Saved Nucleus index cache")
        except Exception as e:
            print("[Spawner] Failed to save cache:", e)


        return index


    def _score_asset(self, query, asset_text):
        query = query.lower()
        asset_text = asset_text.lower()

        score = 0

        # --- basic keyword match ---
        for w in query.split():
            if w in asset_text:
                score += 1

        # --- scene vs prop bias ---
        if "environment" in query or "scene" in query:
            if any(x in asset_text for x in ["environment", "archvis", "scenes", "residential"]):
                score += 3
            if any(x in asset_text for x in ["props", "decor", "furniture"]):
                score -= 2

        # --- prop bias ---
        if any(x in query for x in ["book", "chair", "table", "mug", "lamp"]):
            if any(x in asset_text for x in ["decor", "props", "furniture"]):
                score += 2

        # --- penalize junk ---
        if any(x in asset_text for x in ["thumb", "texture", "material"]):
            score -= 5

        return score

    def _ensure_chat_root(self):
        stage = get_current_stage()
        if not stage.GetPrimAtPath("/World/Chat"):
            UsdGeom.Xform.Define(stage, "/World/Chat")

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


    def _prepare_spawn(self):
        self._ensure_environment()
        self._ensure_chat_root()

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

    def _random_position_in_area(self, area: dict):
        return [
            random.uniform(area["x_min"], area["x_max"]),
            random.uniform(area["y_min"], area["y_max"]),
            area["z"],
        ]
    
    def _random_position_in_default_area(self):
        return self._random_position_in_area(self.DEFAULT_ASSET_AREA)


    def spawn_from_nucleus(self, query, pos=None, area=None):

        banned = ("robot", "unitree", "h1", "scene", "warehouse", "office", "room")
        if any(b in query.lower() for b in banned):
            return f"'{query}' is not a spawnable prop."
        
        self._prepare_spawn()

        index = self._nucleus_index
        if not index:
            return "Assets are still loading. Please try again in a moment."

        scored = [
            (self._score_asset(query, a["text"]), a["path"])
            for a in index
        ]

        scored = sorted(scored, reverse=True)
        scored = [p for s, p in scored if s > 0]

        if not scored:
            return f"No Nucleus asset found for '{query}'"

        usd_path = random.choice(scored[:5])  # diversify

        # if pos is None:
        #     pos = self._random_position_in_default_area()

        if pos is not None:
            final_pos = pos
        elif area and area in self.SEMANTIC_LOCATIONS:
            final_pos = self._random_position_in_area(self.SEMANTIC_LOCATIONS[area])
        else:
            final_pos = self._random_position_in_default_area()


        name = Path(usd_path).stem
        idx = self._next_index(name)
        prim_path = f"/World/Chat/{name}_{idx}"

        add_reference_to_stage(usd_path, prim_path)

        prim = SingleXFormPrim(prim_path)
        prim.set_world_pose(
            position=np.array(final_pos),
            orientation=np.array([1, 0, 0, 0])
        )

        # --- Handle unit-mismatch scaling safely ---
        scale = prim.get_local_scale()

        if scale is not None:
            sx, sy, sz = scale

            # Detect auto unit compensation (cm → m or mm → m)
            if abs(sx - sy) < 1e-6 and abs(sx - sz) < 1e-6:
                if sx in (0.01, 0.001):
                    # Undo unit compensation ONLY
                    prim.set_local_scale(np.array([1.0, 1.0, 1.0]))


        self._spawned_prims.add(prim_path)
        return f"Spawned '{name}' from Nucleus"





    # --------------------------------------------------
    # RESET (FIXED)
    # --------------------------------------------------
    def reset_environment(self):
        # asyncio.ensure_future(self._reset_environment_async())
        
        async_engine.run_coroutine(self._reset_environment_async())

        return "Environment reset scheduled."

    async def _reset_environment_async(self):
        app = omni.kit.app.get_app()
        stage = get_current_stage()
        world = self._world()

        # Let current frame finish
        await app.next_update_async()

        # Remove Chat content
        # if stage and stage.GetPrimAtPath("/World/Chat"):
        #     stage.RemovePrim("/World/Chat")

        # 🔥 Remove ALL children explicitly
        chat_root = stage.GetPrimAtPath("/World/Chat")
        if chat_root:
            for child in list(chat_root.GetChildren()):
                stage.RemovePrim(child.GetPath())

            stage.RemovePrim("/World/Chat")

        await app.next_update_async()

        # Clear physics / scene registry safely
        try:
            world.scene.clear()
        except Exception as e:
            print("[reset] scene.clear warning:", e)

        await app.next_update_async()

        # Recreate Chat root
        if stage and not stage.GetPrimAtPath("/World/Chat"):
            UsdGeom.Xform.Define(stage, "/World/Chat")

        self._spawned_prims.clear()

    
    # --------------------------------------------------
    # BASIC SHAPES TESTING
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

        # pos = (2.2822972338678706, -0.5025799814929452, 1.5654207644517726)
        # orinetation euler 90, 90 0
        # orientation quat 0.5, 0.5, 0.5, 0.5

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
    # def spawn_unitree_at(self, pos=None):
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

    # def _random_position_in_default_area(self):
    #     area = self.DEFAULT_ASSET_AREA
    #     return [
    #         random.uniform(area["x_min"], area["x_max"]),
    #         random.uniform(area["y_min"], area["y_max"]),
    #         area["z"],
    #     ]


    # --------------------------------------------------
    # SCENES (NO articulation, NO physics add)
    # --------------------------------------------------
    # def spawn_scene(self, name):
    #     self._ensure_chat_root()
    #     stage = get_current_stage()

    #     for k, usd in self.ASSET_LIBRARY.items():
    #         if k in name:
    #             prim = f"/World/Chat/Scene_{k}"
    #             if stage.GetPrimAtPath(prim):
    #                 return f"{k} scene already loaded."

    #             add_reference_to_stage(str(usd), prim)
    #             self._spawned_prims.add(prim)
    #             return f"{k} scene loaded."

    #     return f"Unknown scene: {name}"
    # def spawn_scene(self, name):
    #     self._ensure_chat_root()
    #     stage = get_current_stage()
    #     name = name.lower()

    #     # 1️⃣ Try legacy hardcoded scenes first (safe)
    #     for k, usd in self.ASSET_LIBRARY.items():
    #         if k in name:
    #             prim = f"/World/Chat/Scene_{k}"
    #             if stage.GetPrimAtPath(prim):
    #                 return f"{k} scene already loaded."

    #             add_reference_to_stage(str(usd), prim)
    #             self._spawned_prims.add(prim)
    #             return f"{k} scene loaded."

    #     # 2️⃣ Fallback to Nucleus search (NEW)
    #     result = self.spawn_from_nucleus(name)

    #     if result.startswith("No Nucleus"):
    #         return f"Unknown scene: {name}"

    #     return result

    def resolve_scene_name(self, user_text: str) -> str | None:
        text = user_text.lower()

        # Exact ID match first
        if text in self.SCENE_LIBRARY:
            return text

        # Alias match
        for scene_id, aliases in self.SCENE_ALIASES.items():
            for phrase in aliases:
                if phrase in text:
                    return scene_id

        # Fallback partial match
        for scene_id in self.SCENE_LIBRARY:
            if scene_id.replace("_", " ") in text:
                return scene_id

        return None


    def spawn_scene(self, name: str):
        self._ensure_chat_root()
        stage = get_current_stage()

        resolved = self.resolve_scene_name(name)
        if not resolved:
            return f"Unknown scene: {name}"

        prim = f"/World/Chat/Scene_{resolved}"
        if stage.GetPrimAtPath(prim):
            return f"{resolved} scene already loaded."

        add_reference_to_stage(self.SCENE_LIBRARY[resolved], prim)
        self._spawned_prims.add(prim)
        return f"{resolved} scene loaded."




    # --------------------------------------------------
    # SCENES (PROPS ASSETS LIKE TABLE, MUG, ETC)
    # --------------------------------------------------
    def spawn_asset_at(self, name: str, pos=None, location=None):
        self._prepare_spawn()

        if not name:
            return "No object specified."

        name = name.lower().strip()

        # ----------------------------
        # 1. Exact match
        # ----------------------------
        if name in self.ASSET_LIBRARY:
            chosen_name = name

        else:
            # ----------------------------
            # 2. Partial / keyword match
            #    e.g. "mug" → ["yellow mug", "black mug"]
            # ----------------------------
            matches = [
                k for k in self.ASSET_LIBRARY.keys()
                if name in k
            ]

            if matches:
                chosen_name = random.choice(matches)
            else:
                available = ", ".join(self.ASSET_LIBRARY.keys())
                return (
                    f"Asset not available: '{name}'. "
                    f"For example, try: {available}"
                )
        
        # ----------------------------
        # Semantic location override
        # ----------------------------
        # if location in self.SEMANTIC_LOCATIONS:
        #     pos = list(random.choice(self.SEMANTIC_LOCATIONS[location]))


        # ----------------------------
        # Spawn chosen asset
        # ----------------------------
        # DEFAULT_ASSET_POSITION = [1.756650568756057, 0.0, 1.0909934857926475]

        if pos is not None:
            final_pos = pos

        elif location and location in self.SEMANTIC_LOCATIONS:
            final_pos = self._random_position_in_area(
                self.SEMANTIC_LOCATIONS[location]
            )

        else:
            final_pos = self._random_position_in_default_area()


        idx = self._next_index(chosen_name.replace(" ", "_"))
        prim_path = f"/World/Chat/{chosen_name.replace(' ', '_')}_{idx}"

        add_reference_to_stage(self.ASSET_LIBRARY[chosen_name], prim_path)

        prim = SingleXFormPrim(prim_path)

        # Set pose exactly as per Isaac Sim API
        prim.set_world_pose(
            position=np.array(final_pos),
            orientation=np.array([1.0, 0.0, 0.0, 0.0])  # identity quaternion
        )


        self._spawned_prims.add(prim_path)

        return f"{chosen_name} spawned at {final_pos}"


    def remove_from_chat(self, query: str):
        """
        Removes the best-matching asset under /World/Chat,
        even if the semantic object is nested.
        """
        stage = get_current_stage()
        query = query.lower()

        chat_root = "/World/Chat"
        chat_prim = stage.GetPrimAtPath(chat_root)
        if not chat_prim:
            return "No objects to remove."

        candidates = []

        # Traverse everything under /World/Chat
        for prim in stage.Traverse():
            path = prim.GetPath().pathString

            if not path.startswith(chat_root + "/"):
                continue

            name = prim.GetName().lower()

            # Simple keyword match
            score = sum(1 for w in query.split() if w in name)
            if score == 0:
                continue

            # Walk UP to find direct child of /World/Chat
            p = prim
            while p:
                parent = p.GetParent()
                if parent and parent.GetPath().pathString == chat_root:
                    root_candidate = p.GetPath().pathString
                    candidates.append((score, root_candidate))
                    break
                p = parent

        if not candidates:
            return f"No matching object found for '{query}'."

        # Pick best match
        candidates.sort(reverse=True)
        _, prim_path = candidates[0]

        stage.RemovePrim(prim_path)
        self._spawned_prims.discard(prim_path)

        return f"Removed '{Path(prim_path).name}'."
    

    # async def remove_scene_clean_async(self, scene_name: str) -> str:
    #     stage = get_current_stage()
    #     app = omni.kit.app.get_app()

    #     scene_path = f"/World/Chat/Scene_{scene_name}"
    #     root = stage.GetPrimAtPath(scene_path)
    #     if not root or not root.IsValid():
    #         return f"No scene '{scene_name}' found at {scene_path}"

    #     # 1) STOP physics/timeline before touching physics prims
    #     tl = omni.timeline.get_timeline_interface()
    #     try:
    #         tl.stop()
    #     except Exception:
    #         pass

    #     # Let stop propagate
    #     await app.next_update_async()

    #     # 2) Disable physics + unload payloads + break composition (deepest-first)
    #     paths = self._collect_subtree_paths(root)
    #     for p in paths:
    #         prim = stage.GetPrimAtPath(p)
    #         if prim and prim.IsValid():
    #             self._disable_physics_apis(prim)
    #             self._break_composition(prim)

    #     # Let schema changes propagate
    #     await app.next_update_async()

    #     # 3) Delete the root prim via Kit command (more reliable than stage.RemovePrim)
    #     try:
    #         omni.kit.commands.execute("DeletePrims", paths=[scene_path])
    #     except Exception:
    #         # Fallback
    #         stage.RemovePrim(scene_path)

    #     # 4) Flush updates twice (USD + PhysX)
    #     await app.next_update_async()
    #     await app.next_update_async()

    #     # 5) Best-effort PhysX refresh (version-dependent, so guard it)
    #     try:
    #         physx = _physx.get_physx_interface()
    #         # Some builds expose one of these; harmless if missing
    #         for fn in ("force_load_physics_from_usd", "reset_simulation", "reset_physics", "rebuild_collisions"):
    #             if hasattr(physx, fn):
    #                 getattr(physx, fn)()
    #                 break
    #     except Exception:
    #         pass

    #     return f"Scene '{scene_name}' removed cleanly."



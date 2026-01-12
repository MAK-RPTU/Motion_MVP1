from .spawner import Spawner
from .llm_client import LLMClient
from omni.isaac.core.utils.stage import is_stage_loading
import time
import asyncio
from .robot_task_controller import RobotTaskController
import omni.kit.app
import omni.kit.async_engine as async_engine

class ChatController:

    def __init__(self):
        self.spawner = Spawner()
        self.llm = LLMClient()
        self.robot_ctrl = RobotTaskController()

        # Build Nucleus index in background
        # asyncio.ensure_future(self.spawner.build_nucleus_index_async())
        async_engine.run_coroutine(self.spawner.build_nucleus_index_async())

    def _safe_position(self, pos):
        if isinstance(pos, (list, tuple)) and len(pos) == 3:
            try:
                return [float(pos[0]), float(pos[1]), float(pos[2])]
            except Exception:
                pass
        return [0.0, 0.0, 0.0]

    def normalize_prompt(self, text: str) -> str:
        t = text.lower()

        # common typos
        corrections = {
            "fbread": "bread",
            "brad": "bread",
            "bred": "bread",
            "factroy": "factory",
            "warehous": "warehouse",
        }

        for k, v in corrections.items():
            t = t.replace(k, v)

        return t

    async def _remove_object_async(self, obj: str, responses: list):
        
        app = omni.kit.app.get_app()

        # Frame 1: request removal
        msg = self.spawner.remove_from_chat(obj)
        responses.append(msg)

        # Frame 2: let USD process deletion
        await app.next_update_async()

        # Frame 3: extra flush for referenced scenes
        await app.next_update_async()

    async def _remove_scene_async(self, scene_id: str, responses: list):
        msg = await self.spawner.remove_scene_clean_async(scene_id)
        responses.append(msg)


    def handle_prompt(self, text: str) -> str:

        text = self.normalize_prompt(text)
        text_lower = text.lower().strip()

        # if text_lower in ["reset", "clear", "clean environment"]:
        #     return self.spawner.reset_environment()

        result = self.llm.interpret(text)

        if not isinstance(result, (dict, list)):
            return f"LLM Error: Unexpected response format: {result}"

        # Normalize to a list of dicts
        if isinstance(result, dict):
            commands = [result]
        else:
            commands = [c for c in result if isinstance(c, dict)]

        if not commands:
            return "LLM did not return a valid command."

        # cmd = commands[0]  # Only execute one command (by design)

        responses = []

        scene_loaded = False

        for cmd in commands:
            action = cmd.get("action")

            if action == "load_scene":
                responses.append(self.spawner.spawn_scene(cmd["scene"]))

                # Wait for stage to fully load before spawning robot
                while is_stage_loading():
                    time.sleep(0.1)
                
                scene_loaded = True
            
            # ❌ BLOCK spawning objects if scene was loaded
            if scene_loaded and action == "spawn_object":
                continue

            elif action == "spawn_robot":
                # pos = self._safe_position(cmd.get("position"))
                # responses.append(self.spawner.spawn_unitree_at(pos))
                pos = cmd.get("position")          # may be None
                responses.append(
                    self.spawner.spawn_unitree_at(pos)
                )

            # elif action == "spawn_object":
            #     pos = self._safe_position(cmd.get("position"))
            #     responses.append(self.spawner.spawn_cube_at(pos))

            # elif action == "spawn_object":
            #     obj = cmd.get("object")
            #     pos = cmd.get("position")  # may be None
            #     location = cmd.get("location")  # may be None
            #     responses.append(self.spawner.spawn_asset_at(obj, pos, location))

            # elif action == "spawn_object":
            #     obj = cmd.get("object")
            #     pos = cmd.get("position")  # may be None
            #     location = cmd.get("location")  # reuse this as area

            #     # Use Nucleus-backed spawning
            #     if pos is not None:
            #         responses.append(self.spawner.spawn_from_nucleus(obj, pos=pos, area=location))
            #     else:
            #         responses.append(self.spawner.spawn_from_nucleus(obj))

            # elif action == "spawn_object":
            #     obj = cmd.get("object")
            #     pos = cmd.get("position")      # may be None
            #     location = cmd.get("location") # semantic area (sink, table, etc.)

            #     responses.append(
            #         self.spawner.spawn_from_nucleus(
            #             query=obj,
            #             pos=pos,
            #             area=location
            #         )
            #     )

            elif action == "spawn_object":
                obj = cmd.get("object")

                # 🚨 Scene safety override
                if obj in self.spawner.SCENE_LIBRARY:
                    responses.append(self.spawner.spawn_scene(obj))
                    continue

                responses.append(
                    self.spawner.spawn_from_nucleus(
                        query=obj,
                        pos=cmd.get("position"),
                        area=cmd.get("location")
                    )
                )

            # elif action == "remove_object":
            #     obj = cmd.get("object")
            #     if not obj:
            #         responses.append("No object specified to remove.")
            #     else:
            #         responses.append(self.spawner.remove_from_chat(obj))

            # elif action == "reset_environment":
            #     responses.append(self.spawner.reset_environment())

            elif action == "remove_object":
                obj = cmd.get("object")
                if not obj:
                    responses.append("No object specified to remove.")
                    continue

                if obj in self.spawner.SCENE_LIBRARY:
                    # Queue safe removal on Kit update loop
                    # asyncio.ensure_future(self.spawner.remove_scene_clean_async(obj, resume=True, force_stop=False))
                    async_engine.run_coroutine(self.spawner.remove_scene_clean_async(obj, resume=True, force_stop=False))
            
                    responses.append(f"Removing scene '{obj}' (pausing sim briefly)...")
                else:
                    responses.append(self.spawner.remove_from_chat(obj))



            elif action == "reset_environment":
                responses.append(self.spawner.reset_environment())




            elif action == "robot_task":
                # Acknowledge immediately
                task = cmd.get("task", "deliver")
                obj = cmd.get("object")
                dest = cmd.get("destination")

                if not obj or not dest:
                    responses.append("Robot task missing object or destination.")
                    continue

                responses.append(f"System: Acknowledged. Robot will take '{obj}' to '{dest}'.")

                # Execute dummy controller
                result = self.robot_ctrl.execute_task({
                    "task": task,
                    "object": obj,
                    "destination": dest
                })

                if result.get("ok"):
                    responses.append(f"System: {result.get('message')}")
                else:
                    responses.append(f"System: {result.get('message')}")

  

        return "\n".join(responses)


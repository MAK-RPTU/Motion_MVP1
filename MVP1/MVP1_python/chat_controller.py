from .spawner import Spawner
from .llm_client import LLMClient
from omni.isaac.core.utils.stage import is_stage_loading
import time

class ChatController:

    def __init__(self):
        self.spawner = Spawner()
        self.llm = LLMClient()

    def _safe_position(self, pos):
        if isinstance(pos, (list, tuple)) and len(pos) == 3:
            try:
                return [float(pos[0]), float(pos[1]), float(pos[2])]
            except Exception:
                pass
        return [0.0, 0.0, 0.0]


    def handle_prompt(self, text: str) -> str:
        text_lower = text.lower().strip()

        if text_lower in ["reset", "clear", "clean environment"]:
            return self.spawner.reset_environment()

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

        for cmd in commands:
            action = cmd.get("action")

            if action == "load_scene":
                responses.append(self.spawner.spawn_scene(cmd["scene"]))

                # Wait for stage to fully load before spawning robot
                while is_stage_loading():
                    time.sleep(0.1)

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

            elif action == "spawn_object":
                obj = cmd.get("object")
                pos = cmd.get("position")  # may be None
                location = cmd.get("location")  # may be None
                responses.append(self.spawner.spawn_asset_at(obj, pos, location))



        return "\n".join(responses)


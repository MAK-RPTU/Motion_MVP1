# chat_controller.py

# from .spawner import Spawner

# class ChatController:
#     """
#     Handles chat messages and translates them into spawning commands.
#     Modular and replaceable with NLP/LLM later.
#     """

#     def __init__(self):
#         self.spawner = Spawner()

#     def handle_prompt(self, text: str) -> str:
#         """Main router for chat commands."""

#         lower = text.lower()

#         # Simple rule-based "NLP"
#         if "spawn" in lower:
#             return self._handle_spawn(text)

#         return "I don't understand that yet. Try: 'spawn a cube at (0,0,1)'"

#     # ---------------------------------------------------

#     def _handle_spawn(self, text: str):
#         """Parse natural-language-like spawn commands."""

#         # Detect object type
#         if "cube" in text:
#             return self.spawner.spawn_cube(text)

#         if "sphere" in text:
#             return self.spawner.spawn_sphere(text)

#         if "robot" in text or "franka" in text:
#             return self.spawner.spawn_franka(text)

#         return "Spawn what? Try 'spawn cube at (0,0,1)'"


from .spawner import Spawner
from .llm_client import LLMClient

class ChatController:

    def __init__(self):
        self.spawner = Spawner()
        self.llm = LLMClient()  # NEW

    def handle_prompt(self, text: str) -> str:
        """
        Send prompt to LLM → returns structured JSON → spawner executes it.
        """

        print("[ChatController] Sending to LLM:", text)
        result = self.llm.interpret(text)

        if "error" in result:
            return f"LLM Error: {result['error']}"

        # Example JSON result:
        # { "action": "spawn", "object": "cube", "position": [0,0,1] }

        action = result.get("action")
        obj = result.get("object")
        pos = result.get("position", [0,0,0])

        if action == "spawn":
            if obj == "cube":
                return self.spawner.spawn_cube_at(pos)

            if obj == "sphere":
                return self.spawner.spawn_sphere_at(pos)

            if obj in ["franka", "robot"]:
                return self.spawner.spawn_franka_at(pos)

            return f"Unknown object: {obj}"

        return f"Unknown action: {action}"

# llm_client.py
import google.generativeai as genai
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import re

# Load environment variables from the .env file
# Get the path of the current file's directory
current_dir = Path(__file__).parent
# Look for .env in the same directory as this script
dotenv_path = current_dir / ".env"

# Load with an explicit path
load_dotenv(dotenv_path=dotenv_path)

class LLMClient:
    """
    Handles all communication with Gemini (or other LLMs).
    Converts natural-language prompts into structured JSON commands.
    """

    # def __init__(self, api_key="AIzaSyDKi1nW26G0zm2btw4LFFM0219HwpQZQy8", model="gemini-2.5-pro"):
    #     self.api_key = api_key or os.getenv("AIzaSyDKi1nW26G0zm2btw4LFFM0219HwpQZQy8")
    def __init__(self, model="gemini-2.5-pro"):
    # def __init__(self, model="gemini-2.0-flash"):
        # Retrieve the key from the environment
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key is None:
            print("[LLMClient] ERROR: Missing GEMINI_API_KEY!")
        genai.configure(api_key=self.api_key)

        self.model = genai.GenerativeModel(model)

        # System guidelines
        self.system_prompt = """
            You control Isaac Sim.

            Convert user commands into JSON arrays of actions.

            Intent mapping rules:

            The following words or phrases ALL mean "spawn_object":
            - spawn
            - add
            - insert
            - place
            - put
            - create
            - bring
            - I need
            - I want
            - give me
            - show me
            - load an object
            - drop

            The following words or phrases ALL mean "remove_object":
            - remove
            - delete
            - clear
            - get rid of
            - take away
            - discard
            - erase
            - undo
            - remove from the scene

            The following words or phrases ALL mean "reset_environment":
            - reset
            - clear everything
            - clear the scene
            - clean the environment
            - wipe the scene
            - remove everything
            - delete all objects
            - start fresh
            - start over
            - new scene

            Valid actions:
            - load_scene { scene }
            - spawn_robot { robot, position }
            - spawn_object { object, position, location }
            - remove_object { object }
            - reset_environment

            Location rules:
            - location is a semantic place such as "sink", "table", "floor"
            - If a semantic location is mentioned, include "location"
            - Do NOT invent numeric coordinates for locations


            Position rules:
            - position must be a list of 3 numbers: [x, y, z]
            - Only include "position" if the user explicitly specifies coordinates
            - If no position is mentioned, omit the field entirely

            Examples:

            User: Spawn a robot at position (1, 0, 0)
            [
            {"action": "spawn_robot", "robot": "unitree", "position": [1, 0, 0]}
            ]

            User: Spawn a mug in the sink
            [
            {"action": "spawn_object", "object": "mug", "location": "sink"}
            ]

            User: Spawn a robot in a kitchen
            [
            {"action": "load_scene", "scene": "kitchen"},
            {"action": "spawn_robot", "robot": "unitree"}
            ]
            User: Spawn a robot in a office
            [
            {"action": "load_scene", "scene": "office"},
            {"action": "spawn_robot", "robot": "unitree"}
            ]

            User: Spawn a robot in a room
            [
            {"action": "load_scene", "scene": "room"},
            {"action": "spawn_robot", "robot": "unitree"}
            ]
            Only output JSON. No explanations.

            User: Remove the book
            [
            {"action": "remove_object", "object": "book"}
            ]

            User: Delete the robot
            [
            {"action": "remove_object", "object": "unitree"}
            ]

            User: Add a mug to the environment
            [
            {"action": "spawn_object", "object": "mug"}
            ]

            User: I need a chair in the room
            [
            {"action": "spawn_object", "object": "chair"}
            ]

            User: Put a book on the table
            [
            {"action": "spawn_object", "object": "book", "location": "table"}
            ]

            User: Insert a lamp
            [
            {"action": "spawn_object", "object": "lamp"}
            ]

            User: Get rid of the book
            [
            {"action": "remove_object", "object": "book"}
            ]

            User: Delete the chair from the scene
            [
            {"action": "remove_object", "object": "chair"}
            ]

            User: Clear the robot
            [
            {"action": "remove_object", "object": "unitree"}
            ]

            User: Reset the scene
            [
            {"action": "reset_environment"}
            ]

            User: Clear the whole environment
            [
            {"action": "reset_environment"}
            ]

            User: I want to start fresh
            [
            {"action": "reset_environment"}
            ]

            User: Delete everything from the scene
            [
            {"action": "reset_environment"}
            ]

            """



    # ------------------------------------------------------------------

    def _call_api(self, prompt: str) -> str:
        """
        Sends the prompt to Gemini and returns the raw text response.
        """
        full_prompt = self.system_prompt + "\nUser: " + prompt

        try:
            response = self.model.generate_content(full_prompt)

            if hasattr(response, "text"):
                return response.text

            # Some Gemini versions return candidates instead
            return response.candidates[0].content.parts[0].text

        except Exception as e:
            print("[LLM ERROR] Gemini API call failed:", e)
            return '{"action": "error", "message": "LLM API failure"}'


    def interpret(self, prompt):
        raw = self._call_api(prompt)         # however you call Gemini
        result = self._extract_json(raw)     # extract clean JSON
        return result


    # def interpret(self, user_prompt: str) -> dict:
    #     """Calls LLM and returns a dict."""

    #     full_prompt = self.system_prompt + "\nUser: " + user_prompt
        
    #     try:
    #         response = self.model.generate_content(full_prompt)
    #         text = response.text
    #         print("[LLM RAW RESPONSE]", text)

    #         # Parse JSON from response
    #         return json.loads(text)

    #     except Exception as e:
    #         print("[LLM ERROR]", e)
    #         return {"error": str(e)}

    
    def _extract_json(self, text):
        """Extracts and parses JSON from LLM output, even if it contains markdown."""
        try:
            # Remove ```json or ``` fences
            text = re.sub(r"```.*?```", lambda m: m.group(0).strip("`"), text, flags=re.S)

            # Try to extract a JSON array first
            array_match = re.search(r"\[[\s\S]*\]", text)
            if array_match:
                json_str = array_match.group(0)
                return json.loads(json_str)

            # Fall back to extracting a single JSON object
            obj_match = re.search(r"\{[\s\S]*\}", text)
            if obj_match:
                json_str = obj_match.group(0)
                return json.loads(json_str)

            raise ValueError("No JSON found (neither object nor array)")

        except Exception as e:
            print("[LLM ERROR]", e)
            print("[RAW LLM OUTPUT]", text)
            # Return a consistent error dict using 'error' key
            return {"error": str(e)}

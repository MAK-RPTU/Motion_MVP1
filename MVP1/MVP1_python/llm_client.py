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
    # def __init__(self, model="gemini-2.5-pro"):
    def __init__(self, model="gemini-2.0-flash"):
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

            Valid actions:
            - load_scene { scene }
            - spawn_robot { robot, position }
            - spawn_object { object, position }

            Position rules:
            - position must be a list of 3 numbers: [x, y, z]
            - Only include "position" if the user explicitly specifies coordinates
            - If no position is mentioned, omit the field entirely

            Examples:

            User: Spawn a robot at position (1, 0, 0)
            [
            {"action": "spawn_robot", "robot": "unitree", "position": [1, 0, 0]}
            ]

            User: Spawn a robot in a kitchen
            [
            {"action": "load_scene", "scene": "kitchen"},
            {"action": "spawn_robot", "robot": "unitree"}
            ]

            Only output JSON. No explanations.

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

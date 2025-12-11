# llm_client.py
import google.generativeai as genai
import os
import json
import re

class LLMClient:
    """
    Handles all communication with Gemini (or other LLMs).
    Converts natural-language prompts into structured JSON commands.
    """

    def __init__(self, api_key="AIzaSyDKi1nW26G0zm2btw4LFFM0219HwpQZQy8", model="gemini-2.5-pro"):
        self.api_key = api_key or os.getenv("AIzaSyDKi1nW26G0zm2btw4LFFM0219HwpQZQy8")
        if self.api_key is None:
            print("[LLMClient] ERROR: Missing GEMINI_API_KEY!")
        genai.configure(api_key=self.api_key)

        self.model = genai.GenerativeModel(model)

        # System guidelines
        self.system_prompt = """
        You are an Isaac Sim Robotics Assistant.
        Convert natural-language commands into JSON like:
        {
            "action": "spawn",
            "object": "cube",
            "color": "red",
            "position": [0,0,1]
        }
        Only output JSON. No extra text.
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

            # Extract JSON substring
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)

            raise ValueError("No JSON object found")

        except Exception as e:
            print("[LLM ERROR]", e)
            print("[RAW LLM OUTPUT]", text)
            return {"action": "error", "message": "LLM response was invalid JSON"}

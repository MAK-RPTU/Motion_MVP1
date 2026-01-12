# prompt_api.py

from fastapi import FastAPI
from pydantic import BaseModel
import threading
import uvicorn
import carb
import queue
import asyncio

import omni.kit.app
import omni.kit.async_engine as async_engine

from .chat_controller import ChatController
import logging

logger = logging.getLogger("uvicorn.error")
# -----------------------------------------------------------------------------
# Globals
# -----------------------------------------------------------------------------
app = FastAPI()
_prompt_queue = queue.Queue()
_server_started = False
_server = None
_server_thread = None

_controller = None  # Created lazily inside Isaac context


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class PromptRequest(BaseModel):
    prompt: str


class PromptResponse(BaseModel):
    response: str


# -----------------------------------------------------------------------------
# FastAPI endpoint (WEB THREAD ONLY)
# -----------------------------------------------------------------------------
@app.post("/prompt", response_model=PromptResponse)
def send_prompt(req: PromptRequest):

    prompt = req.prompt.strip()

    # 🚑 FILTER HEALTH / KEEPALIVE
    if prompt.lower() in {"ping", "pong", "health", "ok"}:
        return {"response": "ok"}

    
    logging.getLogger("uvicorn.error").warning(
        f"[API] REAL PROMPT >>>{repr(prompt)}<<<"
    )
    # 2. Isaac-specific log
    carb.log_warn(f"[API] REAL PROMPT >>>{prompt}<<<")
    

    # Put prompt in queue for Isaac main thread
    _prompt_queue.put(prompt)

    return {"response": "Prompt received and queued."}


# -----------------------------------------------------------------------------
# Isaac-safe prompt processing (MAIN THREAD)
# -----------------------------------------------------------------------------
async def _process_prompts_async():
    global _controller

    # Create controller inside Kit context
    if _controller is None:
        _controller = ChatController()
        carb.log_info("[API] ChatController initialized")

    app_kit = omni.kit.app.get_app()

    while True:
        try:
            prompt = _prompt_queue.get_nowait()
        except queue.Empty:
            await app_kit.next_update_async()
            continue

        carb.log_info(f"[API] Processing prompt in Isaac thread: {prompt}")

        try:
            result = _controller.handle_prompt(prompt)
            carb.log_info(f"[API] Result: {result}")
        except Exception as e:
            carb.log_error(f"[API] Error handling prompt: {e}")

        await app_kit.next_update_async()


# -----------------------------------------------------------------------------
# Uvicorn server
# -----------------------------------------------------------------------------
def _start_uvicorn():
    global _server
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8211,
        log_level="info",
    )
    _server = uvicorn.Server(config)
    _server.run()


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def start_server_thread():
    global _server_started, _server_thread

    if _server_started:
        carb.log_warn("[API] Server already running, skipping start")
        return

    _server_started = True

    carb.log_info("[API] Starting FastAPI server on port 8211")

    _server_thread = threading.Thread(
        target=_start_uvicorn,
        daemon=True,
        name="IsaacPromptAPIServer",
    )
    _server_thread.start()

    # Start Isaac-side processing loop
    # asyncio.ensure_future(_process_prompts_async())
    async_engine.run_coroutine(_process_prompts_async())

def stop_server():
    global _server_started, _server

    if _server and _server.started:
        carb.log_info("[API] Stopping FastAPI server")
        _server.should_exit = True

    _server_started = False

import json
import traceback
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .orchestrator import run_task
from .config import settings

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

database.init_db()

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "static"


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "model": settings.MODEL_NAME,
             "provider": "groq", "api_key_configured": bool(settings.GROQ_API_KEY)}


@app.get("/api/tasks")
def list_tasks():
    return database.list_tasks()


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    task = database.get_task(task_id)
    if not task:
        return {"error": "not found"}
    return task


@app.websocket("/ws/task")
async def ws_task(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            goal = payload.get("goal", "").strip()
            if not goal:
                await websocket.send_json({"agent": "supervisor", "kind": "error", "content": "Empty goal."})
                continue

            task_id = database.create_task(goal)
            await websocket.send_json({"agent": "supervisor", "kind": "task_started", "content": task_id})

            try:
                async for event in run_task(task_id, goal):
                    await websocket.send_json({"task_id": task_id, **event.to_dict()})
            except Exception as e:
                database.update_task_status(task_id, "failed", str(e))
                await websocket.send_json({
                    "task_id": task_id, "agent": "supervisor", "kind": "error",
                    "content": f"{e}\n{traceback.format_exc()[-800:]}",
                })
    except WebSocketDisconnect:
        pass


# Serve the frontend as static files (single-container deploy)
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

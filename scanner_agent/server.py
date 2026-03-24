"""
BioSecureGate Scanner Agent – WebSocket server.

Runs on the officer's local machine. The web frontend connects via
ws://localhost:9100/ws to capture fingerprints from hardware scanners.

Usage:
    python -m scanner_agent.server
    python -m scanner_agent.server --backend wbf --port 9100
"""

import argparse
import asyncio
import base64
import json
import logging
import sys

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from scanner_agent.backends import get_backend, ScannerBackend

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
log = logging.getLogger("scanner-agent")

app = FastAPI(title="BioSecureGate Scanner Agent")

# Allow any origin — the agent runs on localhost, browser needs CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Will be set at startup
_backend: ScannerBackend = None  # type: ignore


@app.on_event("startup")
async def _startup():
    log.info("Scanner agent ready — backend: %s", _backend.name)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "scanner": _backend.name,
        "available": _backend.is_available(),
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    await ws.send_json({"event": "ready", "scanner": _backend.name})
    log.info("Client connected")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"event": "error", "message": "Invalid JSON"})
                continue

            action = msg.get("action", "")

            if action == "status":
                await ws.send_json({
                    "event": "status",
                    "connected": True,
                    "scanner": _backend.name,
                    "available": _backend.is_available(),
                })

            elif action == "scan":
                await ws.send_json({
                    "event": "scanning",
                    "message": "Place finger on scanner...",
                })
                try:
                    image_bytes = await _backend.capture()
                    image_b64 = base64.b64encode(image_bytes).decode("ascii")
                    await ws.send_json({
                        "event": "captured",
                        "image_base64": image_b64,
                        "scanner": _backend.name,
                    })
                    log.info("Fingerprint captured (%d bytes)", len(image_bytes))
                except Exception as e:
                    log.error("Capture failed: %s", e)
                    await ws.send_json({"event": "error", "message": str(e)})

            elif action == "cancel":
                await ws.send_json({"event": "cancelled", "message": "Scan cancelled"})

            else:
                await ws.send_json({
                    "event": "error",
                    "message": f"Unknown action: {action}",
                })

    except WebSocketDisconnect:
        log.info("Client disconnected")


def main():
    parser = argparse.ArgumentParser(description="BioSecureGate Scanner Agent")
    parser.add_argument("--backend", type=str, default=None,
                        choices=["wbf", "usb", "mock"],
                        help="Scanner backend (default: auto-detect)")
    parser.add_argument("--port", type=int, default=9100,
                        help="WebSocket server port (default: 9100)")
    parser.add_argument("--host", type=str, default="127.0.0.1",
                        help="Bind address (default: 127.0.0.1)")
    args = parser.parse_args()

    global _backend
    _backend = get_backend(args.backend)
    log.info("Using scanner backend: %s", _backend.name)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

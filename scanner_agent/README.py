"""
BioSecureGate Scanner Agent
============================
A lightweight WebSocket server that runs on the officer's PC/laptop.
It bridges hardware fingerprint scanners (USB or laptop built-in) to
the web application running in the browser.

Supported scanner backends:
  1. wbf     – Windows Biometric Framework (laptop built-in sensors)
  2. usb     – Generic USB scanners via vendor SDK / image capture
  3. mock    – Simulated scanner for development/testing

Usage:
    python -m scanner_agent.server              # auto-detect scanner
    python -m scanner_agent.server --backend wbf
    python -m scanner_agent.server --backend usb
    python -m scanner_agent.server --backend mock
    python -m scanner_agent.server --port 9100

The agent exposes:
    ws://localhost:9100/ws        – WebSocket endpoint
    http://localhost:9100/health  – Health check

WebSocket protocol (JSON messages):
    Client → Agent:
        {"action": "scan"}                – Start fingerprint capture
        {"action": "status"}              – Get scanner status
        {"action": "cancel"}              – Cancel ongoing scan

    Agent → Client:
        {"event": "ready",     "scanner": "wbf"|"usb"|"mock"}
        {"event": "scanning",  "message": "Place finger on scanner..."}
        {"event": "captured",  "image_base64": "<base64 PNG>", "scanner": "..."}
        {"event": "error",     "message": "..."}
        {"event": "status",    "connected": true, "scanner": "..."}
"""

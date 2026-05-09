/**
 * BioSecureGate – Fingerprint Scanner Client Module
 *
 * Handles all 4 capture methods:
 *   1. image_upload  – Traditional file upload
 *   2. usb_scanner   – USB/portable scanner via local agent WebSocket
 *   3. laptop_scanner– Built-in laptop scanner via local agent WebSocket
 *
 * The local scanner agent runs at ws://localhost:9100/ws
 */

const SCANNER_AGENT_URL = "ws://127.0.0.1:9100/ws";
const SCANNER_HEALTH_URL = "http://127.0.0.1:9100/health";

// ─── Scanner Agent Connection ──────────────────────────────────

class ScannerClient {
  constructor(onStatus, onCaptured, onError) {
    this.ws = null;
    this.onStatus = onStatus || (() => {});
    this.onCaptured = onCaptured || (() => {});
    this.onError = onError || (() => {});
    this.connected = false;
    this.scannerType = null;
  }

  /**
   * Check if the local scanner agent is running.
   * @returns {Promise<{available: boolean, scanner: string|null}>}
   */
  async checkAgent() {
    try {
      const resp = await fetch(SCANNER_HEALTH_URL, {
        method: "GET",
        signal: AbortSignal.timeout(3000),
      });
      const data = await resp.json();
      return { available: data.available, scanner: data.scanner };
    } catch {
      return { available: false, scanner: null };
    }
  }

  /**
   * Connect to the local scanner agent via WebSocket.
   * @returns {Promise<void>}
   */
  connect() {
    return new Promise((resolve, reject) => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      this.ws = new WebSocket(SCANNER_AGENT_URL);

      this.ws.onopen = () => {
        this.connected = true;
      };

      this.ws.onmessage = (evt) => {
        let msg;
        try {
          msg = JSON.parse(evt.data);
        } catch {
          return;
        }

        switch (msg.event) {
          case "ready":
            this.scannerType = msg.scanner;
            this.onStatus(`Scanner ready (${msg.scanner})`);
            resolve();
            break;

          case "scanning":
            this.onStatus(msg.message);
            break;

          case "captured":
            this.onCaptured(msg.image_base64, msg.scanner);
            break;

          case "error":
            this.onError(msg.message);
            break;

          case "status":
            this.onStatus(
              msg.connected
                ? `Connected: ${msg.scanner}`
                : "Scanner disconnected"
            );
            break;

          case "cancelled":
            this.onStatus("Scan cancelled");
            break;
        }
      };

      this.ws.onerror = () => {
        this.connected = false;
        this.onError("Cannot connect to scanner agent. Is it running?");
        reject(new Error("Scanner agent connection failed"));
      };

      this.ws.onclose = () => {
        this.connected = false;
        this.onStatus("Scanner disconnected");
      };
    });
  }

  /**
   * Request a fingerprint scan from the connected agent.
   */
  scan() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.onError("Scanner not connected");
      return;
    }
    this.ws.send(JSON.stringify({ action: "scan" }));
  }

  /**
   * Cancel an ongoing scan.
   */
  cancel() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action: "cancel" }));
    }
  }

  /**
   * Disconnect from the agent.
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
  }
}

// ─── Utility: base64 → File for upload ─────────────────────────

/**
 * Convert base64 image data to a File object for FormData upload.
 * @param {string} base64Data
 * @param {string} filename
 * @returns {File}
 */
function base64ToFile(base64Data, filename = "fingerprint.png") {
  const byteChars = atob(base64Data);
  const byteArr = new Uint8Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) {
    byteArr[i] = byteChars.charCodeAt(i);
  }
  return new File([byteArr], filename, { type: "image/png" });
}

// ─── API calls ─────────────────────────────────────────────────

/**
 * Enroll a fingerprint via the backend API.
 * @param {string} apiBase - Backend URL (e.g., "https://your-app.onrender.com")
 * @param {string} token - JWT access token
 * @param {FormData} formData - Must contain: person_id, full_name, image, capture_method
 * @returns {Promise<object>}
 */
async function enrollFingerprint(apiBase, token, formData) {
  // Force v2 endpoint to ensure anti-diagram gates are applied
  const resp = await fetch(`${apiBase}/api/experimental/enroll/fingerprint`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || "Enrollment failed");
  }
  return resp.json();
}

/**
 * Match a fingerprint via the backend API.
 * @param {string} apiBase
 * @param {string} token
 * @param {File} imageFile
 * @returns {Promise<object>}
 */
async function matchFingerprint(apiBase, token, imageFile) {
  const fd = new FormData();
  fd.append("image", imageFile);
  const resp = await fetch(`${apiBase}/api/match/fingerprint`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || "Match failed");
  }
  return resp.json();
}

// ─── Export ────────────────────────────────────────────────────

// For ES module usage
export { ScannerClient, base64ToFile, enrollFingerprint, matchFingerprint };

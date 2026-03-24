import { SCANNER_WS_URL, SCANNER_HEALTH_URL } from "./api-config"

export async function checkScannerHealth(): Promise<boolean> {
  try {
    const res = await fetch(SCANNER_HEALTH_URL, { method: "GET" })
    return res.ok
  } catch {
    return false
  }
}

export function base64ToFile(base64: string, filename = "fingerprint.png"): File {
  const byteString = atob(base64.split(",").pop() || base64)
  const mimeType = "image/png"
  const ab = new ArrayBuffer(byteString.length)
  const ia = new Uint8Array(ab)
  for (let i = 0; i < byteString.length; i++) {
    ia[i] = byteString.charCodeAt(i)
  }
  return new File([ab], filename, { type: mimeType })
}

export class ScannerClient {
  private ws: WebSocket | null = null
  private onImage: ((file: File) => void) | null = null
  private onError: ((error: string) => void) | null = null
  private onStatus: ((status: string) => void) | null = null

  connect(callbacks: {
    onImage: (file: File) => void
    onError: (error: string) => void
    onStatus?: (status: string) => void
  }) {
    this.onImage = callbacks.onImage
    this.onError = callbacks.onError
    this.onStatus = callbacks.onStatus ?? null

    try {
      this.ws = new WebSocket(SCANNER_WS_URL)

      this.ws.onopen = () => {
        this.onStatus?.("Connected to scanner agent")
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === "image" && data.data) {
            const file = base64ToFile(data.data, "fingerprint_scan.png")
            this.onImage?.(file)
          } else if (data.type === "error") {
            this.onError?.(data.message || "Scanner error")
          } else if (data.type === "status") {
            this.onStatus?.(data.message || "")
          }
        } catch {
          this.onError?.("Invalid scanner response")
        }
      }

      this.ws.onerror = () => {
        this.onError?.("Scanner connection error")
      }

      this.ws.onclose = () => {
        this.onStatus?.("Scanner disconnected")
      }
    } catch {
      this.onError?.("Failed to connect to scanner agent")
    }
  }

  scan() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ command: "scan" }))
    }
  }

  disconnect() {
    this.ws?.close()
    this.ws = null
  }
}

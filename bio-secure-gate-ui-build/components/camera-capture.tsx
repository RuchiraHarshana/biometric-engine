"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle, Camera, Zap, StopCircle, RefreshCw } from "lucide-react"

interface CameraCaptureProps {
  onCapture: (file: File) => void
  facingMode?: "user" | "environment"
}

type CamDevice = { deviceId: string; label: string }

export function CameraCapture({ onCapture, facingMode = "user" }: CameraCaptureProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [devices, setDevices] = useState<CamDevice[]>([])
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>("")
  const [stream, setStream] = useState<MediaStream | null>(null)

  const [error, setError] = useState<string | null>(null)
  const [active, setActive] = useState(false)
  const [hasFrames, setHasFrames] = useState(false)
  const [loading, setLoading] = useState(false)

  const isMobile = useMemo(() => {
    if (typeof window === "undefined") return false
    return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
  }, [])

  const stopCamera = () => {
    try {
      stream?.getTracks().forEach((t) => t.stop())
    } catch {}
    if (videoRef.current) videoRef.current.srcObject = null
    setStream(null)
    setActive(false)
    setHasFrames(false)
    setLoading(false)
  }

  const ensurePermissionsAndList = async () => {
    setError(null)
    try {
      // 1) Ask permission once (needed to get device labels on Chrome)
      const temp = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      temp.getTracks().forEach((t) => t.stop())

      // 2) List devices
      const all = await navigator.mediaDevices.enumerateDevices()
      const cams = all
        .filter((d) => d.kind === "videoinput")
        .map((d) => ({ deviceId: d.deviceId, label: d.label || "Camera" }))

      setDevices(cams)

      // Pick default if none selected
      if (!selectedDeviceId && cams.length > 0) {
        // Prefer "Integrated" / "USB" on laptops, otherwise first one
        const preferred =
          cams.find((c) => /integrated|usb|webcam/i.test(c.label)) ||
          cams[0]
        setSelectedDeviceId(preferred.deviceId)
      }
    } catch (e: any) {
      setError(
        "Camera permission denied or blocked. Please allow camera access in browser settings, then refresh."
      )
    }
  }

  const safePlayAndWatchFrames = async (video: HTMLVideoElement) => {
    // wait metadata so dimensions exist
    await new Promise<void>((resolve) => {
      if (video.readyState >= 1) return resolve()
      video.onloadedmetadata = () => resolve()
    })

    try {
      await video.play()
    } catch {
      // ignore autoplay restrictions; user clicked button anyway
    }

    // detect frames (videoWidth/videoHeight > 0)
    const check = () => {
      const v = videoRef.current
      if (!v) return
      const ok = v.videoWidth > 0 && v.videoHeight > 0
      setHasFrames(ok)
      if (!ok) requestAnimationFrame(check)
    }
    requestAnimationFrame(check)
  }

  const startCamera = async () => {
    setError(null)
    setLoading(true)
    setHasFrames(false)

    try {
      // If no device chosen yet, refresh device list
      if (!selectedDeviceId) {
        await ensurePermissionsAndList()
      }

      // IMPORTANT: use deviceId when possible (most reliable)
      const constraints: MediaStreamConstraints = {
        audio: false,
        video: selectedDeviceId
          ? {
              deviceId: { exact: selectedDeviceId },
              width: { ideal: 1280 },
              height: { ideal: 720 },
            }
          : {
              // fallback
              facingMode,
              width: { ideal: 1280 },
              height: { ideal: 720 },
            },
      }

      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints)

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream
        // Mirror only for front camera
        videoRef.current.style.transform = isMobile && facingMode === "environment" ? "none" : "scaleX(-1)"
        await safePlayAndWatchFrames(videoRef.current)
      }

      setStream(mediaStream)
      setActive(true)
    } catch (e: any) {
      const name = e?.name || "CameraError"
      const msg = e?.message || "Unknown camera error"

      setError(
        `Failed to start camera (${name}). ${msg}\n\nFix: In Chrome settings → Camera → select the correct camera device.`
      )
      stopCamera()
    } finally {
      setLoading(false)
    }
  }

  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return
    const video = videoRef.current
    const canvas = canvasRef.current

    if (video.videoWidth === 0 || video.videoHeight === 0) {
      setError("No camera frames yet. Wait 1–2 seconds and try Capture again.")
      return
    }

    canvas.width = video.videoWidth
    canvas.height = video.videoHeight

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

    canvas.toBlob(
      (blob) => {
        if (!blob) return
        const file = new File([blob], "capture.jpg", { type: "image/jpeg" })
        onCapture(file)
        stopCamera()
      },
      "image/jpeg",
      0.95
    )
  }

  useEffect(() => {
    ensurePermissionsAndList()

    // Re-list on device changes (plugging USB cam etc.)
    const onChange = () => ensurePermissionsAndList()
    navigator.mediaDevices?.addEventListener?.("devicechange", onChange)

    return () => {
      navigator.mediaDevices?.removeEventListener?.("devicechange", onChange)
      stopCamera()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="space-y-4">
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="whitespace-pre-line">{error}</AlertDescription>
        </Alert>
      )}

      {/* Camera selector (key fix for black preview) */}
      <div className="space-y-2">
        <label className="text-sm text-muted-foreground">Camera device</label>
        <div className="flex gap-2">
          <select
            className="w-full h-10 rounded-md border border-border bg-background px-3 text-sm"
            value={selectedDeviceId}
            onChange={(e) => setSelectedDeviceId(e.target.value)}
            disabled={active || devices.length === 0}
          >
            {devices.length === 0 ? (
              <option value="">No cameras found</option>
            ) : (
              devices.map((d) => (
                <option key={d.deviceId} value={d.deviceId}>
                  {d.label}
                </option>
              ))
            )}
          </select>

          <Button
            type="button"
            variant="outline"
            className="gap-2"
            onClick={ensurePermissionsAndList}
            disabled={active}
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </Button>
        </div>
      </div>

      {!active && (
        <Button onClick={startCamera} className="w-full gap-2 glassmorphism" size="lg" disabled={loading}>
          <Camera className="w-4 h-4" />
          {loading ? "Starting camera..." : "Open Camera"}
        </Button>
      )}

      {/* Video element is always in DOM so videoRef is available when startCamera runs */}
      <div className="relative rounded-lg overflow-hidden border border-accent/50 glassmorphism" style={{ display: active ? "block" : "none" }}>
        <video ref={videoRef} autoPlay playsInline muted className="w-full h-[320px] object-cover bg-black" />

        <div className="absolute top-3 left-3 px-3 py-1 rounded-full text-xs border border-border bg-black/50">
          {hasFrames ? "Camera Live ✅" : "Starting camera…"}
        </div>
      </div>

      {active && (
        <div className="flex gap-2">
          <Button
            onClick={capturePhoto}
            className="flex-1 gap-2 bg-accent hover:bg-accent/90"
            size="lg"
            disabled={!hasFrames}
          >
            <Zap className="w-4 h-4" />
            Capture
          </Button>

          <Button onClick={stopCamera} variant="outline" className="flex-1 gap-2 glassmorphism" size="lg">
            <StopCircle className="w-4 h-4" />
            Stop
          </Button>
        </div>
      )}

      <canvas ref={canvasRef} className="hidden" />
    </div>
  )
}

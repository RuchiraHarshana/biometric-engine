"use client"
import { useMemo, useState, useRef } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, Camera, Upload, AlertCircle, CheckCircle2, X, Fingerprint, ScanFace, FileWarning } from "lucide-react"
import { matchFace, matchFingerprint, getPersons } from "@/lib/api"
import { ScannerClient, checkScannerHealth } from "@/lib/fingerprint-scanner"
import { CameraCapture } from "@/components/camera-capture"

type MatchMode = "face" | "fingerprint"

interface MatchResult {
  matched: boolean
  person_id?: string
  full_name?: string
  similarity?: number
  threshold?: number
  email?: string
  mobile_number?: string
  address?: string
  criminal_records?: string
  [key: string]: any
}

export function MatchForm() {
  const router = useRouter()
  const [mode, setMode] = useState<MatchMode>("face")
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [showCamera, setShowCamera] = useState(false)
  const [captureMethod, setCaptureMethod] = useState<string>("image_upload")
  const [showScanner, setShowScanner] = useState(false)
  const [scannerStatus, setScannerStatus] = useState<string|null>(null)
  const [scannerError, setScannerError] = useState<string|null>(null)
  const scannerRef = useRef<ScannerClient|null>(null)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<MatchResult | null>(null)
  const [criminalRecords, setCriminalRecords] = useState<string | null>(null)

  const preview = useMemo(() => (imageFile ? URL.createObjectURL(imageFile) : null), [imageFile])

  const clearAll = () => {
    setImageFile(null)
    setError(null)
    setResult(null)
    setScannerError(null)
    setScannerStatus(null)
    setShowScanner(false)
    scannerRef.current?.disconnect()
  }

  // Scanner logic
  const openScanner = async () => {
    setScannerError(null)
    setScannerStatus("Connecting to scanner...")
    setShowScanner(true)
    const healthy = await checkScannerHealth()
    if (!healthy) {
      setScannerError("Scanner agent is not running or not reachable.")
      setScannerStatus(null)
      return
    }
    const scanner = new ScannerClient()
    scannerRef.current = scanner
    scanner.connect({
      onImage: (file) => {
        setImageFile(file)
        setShowScanner(false)
        setScannerStatus(null)
        setScannerError(null)
        scanner.disconnect()
      },
      onError: (err) => {
        setScannerError(err)
        setScannerStatus(null)
      },
      onStatus: (msg) => setScannerStatus(msg)
    })
    setScannerStatus("Connected. Waiting for fingerprint scan...")
    setTimeout(() => {
      scanner.scan()
      setScannerStatus("Place finger on scanner...")
    }, 500)
  }
  const closeScanner = () => {
    setShowScanner(false)
    setScannerStatus(null)
    setScannerError(null)
    scannerRef.current?.disconnect()
  }

  const submitMatch = async () => {
    setError(null)
    setResult(null)

    if (!imageFile) {
      setError(`Please provide a ${mode} image.`)
      return
    }

    try {
      setLoading(true)
      let data
      if (mode === "face") {
        data = await matchFace(imageFile)
      } else {
        data = await matchFingerprint(imageFile, { capture_method: captureMethod })
      }
      setResult(data)
    } catch (e: any) {
      setError(e?.message || "Match failed.")
    } finally {
      setLoading(false)
    }
  }

  // UI rendering (simplified, you may want to further match enroll-form.tsx for parity)
  return (
    <Card className="p-6 space-y-5 bg-card/50 border-border">
      {/* Mode tabs */}
      <div className="flex gap-2 p-1 rounded-lg bg-muted/50">
        <button
          type="button"
          onClick={() => { setMode("face"); clearAll() }}
          className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            mode === "face" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <ScanFace className="w-4 h-4" />
          Face
        </button>
        <button
          type="button"
          onClick={() => { setMode("fingerprint"); clearAll() }}
          className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            mode === "fingerprint" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Fingerprint className="w-4 h-4" />
          Fingerprint
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="break-words">{error}</AlertDescription>
        </Alert>
      )}
      {result && (
        <Alert className={result.matched ? "border-green-500" : ""}>
          <CheckCircle2 className="h-4 w-4" />
          <AlertDescription className="break-words">
            {result.matched ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-lg text-green-700 dark:text-green-400">Match Found</span>
                </div>
                <div className="text-base font-medium">
                  {result.full_name || result.person_id}
                </div>
                {result.person_id && (
                  <div className="text-sm text-muted-foreground font-mono">
                    ID: {result.person_id}
                  </div>
                )}
                <Button
                  variant="destructive"
                  size="sm"
                  className="gap-2 mt-1"
                  onClick={() => {
                    sessionStorage.setItem(`criminal_details_${result.person_id}`, JSON.stringify(result))
                    router.push(`/dashboard/criminal-details/${result.person_id}`)
                  }}
                >
                  <FileWarning className="w-4 h-4" />
                  Criminal Details
                </Button>
              </div>
            ) : (
              <div className="space-y-2">
                <span className="text-red-600 font-semibold">No match found.</span>
                {typeof result.similarity === "number" && (
                  <div className="text-sm text-muted-foreground">
                    Similarity: {result.similarity.toFixed(3)}
                    {typeof result.threshold === "number" ? ` / threshold ${result.threshold.toFixed(3)}` : ""}
                  </div>
                )}
                {result.candidate_full_name || result.candidate_person_id ? (
                  <div className="text-sm text-muted-foreground">
                    Closest candidate: {result.candidate_full_name || result.candidate_person_id}
                  </div>
                ) : null}
                {result.tier ? (
                  <div className="text-xs text-muted-foreground">Tier: {result.tier}</div>
                ) : null}
              </div>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Fingerprint capture method selector */}
      {mode === "fingerprint" && (
        <div className="space-y-2">
          <label className="text-sm font-medium">Capture Method</label>
          <div className="flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => { setCaptureMethod("image_upload"); closeScanner(); }}
              className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                captureMethod === "image_upload"
                  ? "bg-accent/20 border-accent/50 text-accent"
                  : "border-border text-muted-foreground hover:border-accent/30"
              }`}
            >
              Image upload
            </button>
            <button
              type="button"
              onClick={() => { setCaptureMethod("usb_scanner"); openScanner(); }}
              className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                captureMethod === "usb_scanner"
                  ? "bg-accent/20 border-accent/50 text-accent"
                  : "border-border text-muted-foreground hover:border-accent/30"
              }`}
            >
              USB scanner
            </button>
            <button
              type="button"
              onClick={() => { setCaptureMethod("laptop_scanner"); openScanner(); }}
              className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                captureMethod === "laptop_scanner"
                  ? "bg-accent/20 border-accent/50 text-accent"
                  : "border-border text-muted-foreground hover:border-accent/30"
              }`}
            >
              Laptop scanner
            </button>
          </div>
        </div>
      )}

      {/* Scanner panel for fingerprint capture */}
      {showScanner && (
        <div className="p-4 rounded-lg border border-border glassmorphism space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">Fingerprint Scanner</div>
            <Button variant="ghost" size="sm" className="gap-2" onClick={closeScanner}>
              <X className="w-4 h-4" />
              Close
            </Button>
          </div>
          {scannerStatus && (
            <Alert>
              <AlertDescription>{scannerStatus}</AlertDescription>
            </Alert>
          )}
          {scannerError && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{scannerError}</AlertDescription>
            </Alert>
          )}
          <div className="text-xs text-muted-foreground">Follow instructions on the scanner device. The captured fingerprint will appear below.</div>
        </div>
      )}

      {/* Image area */}
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-medium">{mode === "face" ? "Face image" : "Fingerprint image"} *</div>
            <div className="text-xs text-muted-foreground">Upload from phone/PC OR capture using webcam.</div>
          </div>
          {imageFile && (
            <Button variant="outline" size="sm" className="gap-2" onClick={clearAll}>
              <X className="w-4 h-4" />
              Clear
            </Button>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" className="gap-2" onClick={() => setShowCamera(true)}>
            <Camera className="w-4 h-4" />
            Use Camera
          </Button>
          <label className="inline-flex items-center gap-2 px-4 py-2 rounded-md border border-border bg-transparent hover:bg-accent/5 cursor-pointer text-sm">
            <Upload className="w-4 h-4" />
            Upload Image
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => setImageFile(e.target.files?.[0] || null)}
            />
          </label>
        </div>
        {/* Preview */}
        {preview && (
          <div className="rounded-lg overflow-hidden border border-border bg-black/20">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="Preview" className="w-full aspect-video object-cover" />
          </div>
        )}
        {!preview && (
          <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
            No image selected. Use <span className="font-medium">Camera</span> or <span className="font-medium">Upload</span>.
          </div>
        )}
      </div>

      {/* Camera panel */}
      {showCamera && (
        <div className="p-4 rounded-lg border border-border glassmorphism space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">Camera Capture</div>
            <Button variant="ghost" size="sm" className="gap-2" onClick={() => setShowCamera(false)}>
              <X className="w-4 h-4" />
              Close
            </Button>
          </div>
          <CameraCapture
            facingMode={mode === "face" ? "user" : "environment"}
            onCapture={(file) => {
              setImageFile(file)
              setShowCamera(false)
            }}
            onClose={() => setShowCamera(false)}
            onCancel={() => setShowCamera(false)}
          />
        </div>
      )}

      {/* Submit */}
      <Button onClick={submitMatch} disabled={loading} className="w-full">
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Matching...
          </>
        ) : (
          `Match ${mode === "face" ? "Face" : "Fingerprint"}`
        )}
      </Button>
    </Card>
  )
}

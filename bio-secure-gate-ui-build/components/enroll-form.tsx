"use client"

import { useMemo, useState, useRef } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, Camera, Upload, AlertCircle, CheckCircle2, X, Fingerprint, ScanFace } from "lucide-react"
import { enrollFace, enrollFingerprint } from "@/lib/api"
import { CameraCapture } from "@/components/camera-capture"
import { ScannerClient, checkScannerHealth } from "@/lib/fingerprint-scanner"


type EnrollMode = "face" | "fingerprint"

export function EnrollForm() {
        const router = useRouter()
      // Open scanner panel and connect to scanner
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
    // Clear preview and reset states
    const clearPreview = () => {
      setImageFile(null)
      setSuccess(null)
      setError(null)
      setScannerError(null)
      setScannerStatus(null)
    }

    // Handle file selection
    const onPickFile = (f: File | null) => {
      setSuccess(null)
      setError(null)
      setScannerError(null)
      setScannerStatus(null)
      setImageFile(f)
    }

    // Handle form submission
    const onSubmit = async () => {
      setError(null)
      setSuccess(null)

      if (!personId.trim()) {
        setError("person_id is required.")
        return
      }
      if (!imageFile) {
        setError(`${mode === "face" ? "Face" : "Fingerprint"} image is required.`)
        return
      }

      try {
        setLoading(true)
        const personData = {
          full_name: fullName || undefined,
          email: email || undefined,
          mobile_number: mobileNumber || undefined,
          address: address || undefined,
          criminal_records: criminalRecords || undefined,
        }

        let data
        if (mode === "face") {
          data = await enrollFace(personId.trim(), imageFile, personData)
        } else {
          data = await enrollFingerprint(personId.trim(), imageFile, {
            ...personData,
            capture_method: captureMethod,
          })
        }
        setSuccess(data)
        // Redirect to success page after short delay
        setTimeout(() => {
          router.push("/dashboard/enroll/success")
        }, 500)
      } catch (e: any) {
        setError(e?.message || "Enroll failed.")
      } finally {
        setLoading(false)
      }
    }
  const [mode, setMode] = useState<EnrollMode>("face")
  const [personId, setPersonId] = useState("")
  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [mobileNumber, setMobileNumber] = useState("")
  const [address, setAddress] = useState("")
  const [criminalRecords, setCriminalRecords] = useState("")
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [showCamera, setShowCamera] = useState(false)
  const [captureMethod, setCaptureMethod] = useState<string>("image_upload")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<any>(null)
  const [showScanner, setShowScanner] = useState(false)
  const [scannerStatus, setScannerStatus] = useState<string|null>(null)
  const [scannerError, setScannerError] = useState<string|null>(null)
  const scannerRef = useRef<ScannerClient|null>(null)
  const previewUrl = useMemo(() => {
    if (!imageFile) return null
    return URL.createObjectURL(imageFile)
  }, [imageFile])

  const closeScanner = () => {
    setShowScanner(false)
    setScannerStatus(null)
    setScannerError(null)
    scannerRef.current?.disconnect()
  }

  return (
    <Card className="p-6 space-y-5 bg-card/50 border-border">
      {/* Mode tabs */}
      <div className="flex gap-2 p-1 rounded-lg bg-muted/50">
        <button
          type="button"
          onClick={() => { setMode("face"); clearPreview() }}
          className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            mode === "face" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <ScanFace className="w-4 h-4" />
          Face
        </button>
        <button
          type="button"
          onClick={() => { setMode("fingerprint"); clearPreview() }}
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

      {success && (
        <Alert>
          <CheckCircle2 className="h-4 w-4" />
          <AlertDescription className="break-words">
            Enrolled successfully: <span className="font-semibold">{success?.person_id}</span>
          </AlertDescription>
        </Alert>
      )}

      {/* Person fields */}
      <div className="grid gap-4">
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">person_id *</label>
            <Input value={personId} onChange={(e) => setPersonId(e.target.value)} placeholder="e.g. CRM-001" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">full_name</label>
            <Input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="e.g. John Silva" />
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">email</label>
            <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="e.g. john@mail.com" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">mobile_number</label>
            <Input value={mobileNumber} onChange={(e) => setMobileNumber(e.target.value)} placeholder="+94 7X XXX XXXX" />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">address</label>
          <Textarea value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Address (optional)" />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">criminal_records</label>
          <Textarea
            value={criminalRecords}
            onChange={(e) => setCriminalRecords(e.target.value)}
            placeholder="Optional notes (leave empty if none)"
          />
        </div>
      </div>

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
            <Button variant="outline" size="sm" className="gap-2" onClick={clearPreview}>
              <X className="w-4 h-4" />
              Clear
            </Button>
          )}
        </div>

        {/* Buttons */}
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
              onChange={(e) => onPickFile(e.target.files?.[0] || null)}
            />
          </label>
        </div>

        {/* Preview */}
        {previewUrl && (
          <div className="rounded-lg overflow-hidden border border-border bg-black/20">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previewUrl} alt="Preview" className="w-full aspect-video object-cover" />
          </div>
        )}

        {!previewUrl && (
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
      <Button onClick={onSubmit} disabled={loading} className="w-full">
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Enrolling...
          </>
        ) : (
          `Enroll ${mode === "face" ? "Face" : "Fingerprint"}`
        )}
      </Button>
    </Card>
  )
}

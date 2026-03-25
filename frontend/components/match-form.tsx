"use client"

import { useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, Camera, Upload, AlertCircle, CheckCircle2, X, Fingerprint, ScanFace } from "lucide-react"
import { matchFace, matchFingerprint, getPersons } from "@/lib/api"
import { CameraCapture } from "@/components/camera-capture"

type MatchMode = "face" | "fingerprint"

interface MatchResult {
  matched: boolean
  person_id?: string
  full_name?: string
  similarity?: number
  threshold?: number
  criminal_records?: string
}

export function MatchForm() {
  const [mode, setMode] = useState<MatchMode>("face")
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [showCamera, setShowCamera] = useState(false)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<MatchResult | null>(null)
  const [criminalRecords, setCriminalRecords] = useState<string | null>(null)

  const preview = useMemo(() => (imageFile ? URL.createObjectURL(imageFile) : null), [imageFile])

  const clearAll = () => {
    setImageFile(null)
    setError(null)
    setResult(null)
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
      const data = mode === "face" ? await matchFace(imageFile) : await matchFingerprint(imageFile)
      setResult(data)
      setCriminalRecords(null)
      if (data.matched && data.person_id) {
        // Fetch person details to get criminal records
        try {
          const persons = await getPersons();
          const person = Array.isArray(persons)
            ? persons.find((p) => p.person_id === data.person_id)
            : null;
          if (person && person.criminal_records) {
            setCriminalRecords(person.criminal_records);
          }
        } catch (e) {
          // ignore fetch error
        }
      }
    } catch (e: any) {
      setError(e?.message || "Match failed.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="p-6 space-y-6 bg-card/50 border-border">
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
          Face Match
        </button>
        <button
          type="button"
          onClick={() => { setMode("fingerprint"); clearAll() }}
          className={`flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            mode === "fingerprint" ? "bg-background shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Fingerprint className="w-4 h-4" />
          Fingerprint Match
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
        <Alert className={result.matched ? "border-green-500/40 bg-green-500/10" : "border-destructive/40"}>
          {result.matched ? <CheckCircle2 className="h-4 w-4 text-green-500" /> : <AlertCircle className="h-4 w-4" />}
          <AlertDescription className="break-words">
            <div className="font-semibold">{result.matched ? "Match Found" : "No Match"}</div>
            {result.matched && result.full_name && (
              <div className="text-xs mt-1">
                {result.full_name} ({result.person_id}) — Similarity: {((result.similarity ?? 0) * 100).toFixed(1)}%
              </div>
            )}
            {result.matched && criminalRecords && (
              <div className="text-xs mt-2 text-red-600">
                <span className="font-semibold">Criminal Records:</span> {criminalRecords}
              </div>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Image section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {mode === "face" ? <ScanFace className="w-4 h-4 text-accent" /> : <Fingerprint className="w-4 h-4 text-accent" />}
            <div>
              <div className="text-sm font-semibold">{mode === "face" ? "Face" : "Fingerprint"} Image</div>
              <div className="text-xs text-muted-foreground">Upload or capture an image to search</div>
            </div>
          </div>

          {imageFile && (
            <Button variant="outline" size="sm" onClick={clearAll} className="gap-2">
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
              onChange={(e) => {
                setResult(null)
                setImageFile(e.target.files?.[0] || null)
              }}
            />
          </label>
        </div>

        {preview ? (
          <div className="rounded-lg overflow-hidden border border-border bg-black/20">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="Preview" className="w-full aspect-video object-cover" />
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">
            No image selected.
          </div>
        )}

        {showCamera && (
          <div className="p-4 rounded-lg border border-border glassmorphism space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-sm font-semibold">Capture {mode === "face" ? "Face" : "Fingerprint"}</div>
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
                setResult(null)
              }}
              onClose={() => setShowCamera(false)}
              onCancel={() => setShowCamera(false)}
            />
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-2">
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

        <Button variant="outline" className="w-full" onClick={clearAll}>
          Reset
        </Button>
      </div>

      {/* Result details */}
      {result && (
        <div className="rounded-lg border border-border p-4 bg-background/30 space-y-2">
          <div className="text-sm font-semibold">Match Details</div>
          <div className="grid gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Matched</span>
              <span className="font-mono">{String(result.matched)}</span>
            </div>
            {result.person_id && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Person ID</span>
                <span className="font-mono">{result.person_id}</span>
              </div>
            )}
            {result.full_name && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Name</span>
                <span className="font-medium">{result.full_name}</span>
              </div>
            )}
            {result.similarity !== undefined && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Similarity</span>
                <span className="font-mono">{(result.similarity * 100).toFixed(1)}%</span>
              </div>
            )}
            {result.threshold !== undefined && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Threshold</span>
                <span className="font-mono">{result.threshold}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}

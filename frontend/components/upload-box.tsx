"use client"

import type React from "react"

import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Upload, AlertCircle } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface UploadBoxProps {
  onFileSelect: (file: File) => void
  accept?: string
  label?: string
}

export function UploadBox({ onFileSelect, accept = "image/*", label = "Upload Image" }: UploadBoxProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFile = (file: File) => {
    if (file.type.startsWith("image/")) {
      setError(null)
      onFileSelect(file)
    } else {
      setError("Please select an image file")
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.currentTarget.files?.[0]
    if (file) handleFile(file)
  }

  return (
    <div className="space-y-3">
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div
        onDrop={handleDrop}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        className={`glassmorphism rounded-lg p-8 text-center border-2 border-dashed transition-all ${
          isDragging ? "border-accent bg-accent/10" : "border-border"
        }`}
      >
        <input ref={inputRef} type="file" accept={accept} onChange={handleChange} className="hidden" />
        <div className="space-y-3">
          <Upload className={`w-8 h-8 mx-auto ${isDragging ? "text-accent" : "text-muted-foreground"}`} />
          <div>
            <p className="font-medium">Drag & drop your image</p>
            <p className="text-sm text-muted-foreground">or</p>
          </div>
          <Button type="button" onClick={() => inputRef.current?.click()} className="gap-2">
            <Upload className="w-4 h-4" />
            {label}
          </Button>
        </div>
      </div>
    </div>
  )
}

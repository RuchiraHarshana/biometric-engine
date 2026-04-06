"use client"

import Image from "next/image"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { CheckCircle2, AlertCircle, User } from "lucide-react"
import { API_ENDPOINTS } from "@/lib/api-config"

interface ResultCardProps {
  result: {
    matched: boolean
    person_id?: string
    full_name?: string
    similarity?: number
    threshold?: number
    access_granted?: boolean
    decision_rule?: string
  } | null
  isLoading?: boolean
}

export function ResultCard({ result, isLoading }: ResultCardProps) {
  if (isLoading) {
    return (
      <Card className="glassmorphism p-6 neon-border">
        <div className="space-y-4">
          <div className="h-40 bg-muted/20 rounded-lg animate-pulse" />
          <div className="space-y-2">
            <div className="h-4 bg-muted/20 rounded w-3/4 animate-pulse" />
            <div className="h-4 bg-muted/20 rounded w-1/2 animate-pulse" />
          </div>
        </div>
      </Card>
    )
  }

  if (!result) {
    return (
      <Card className="glassmorphism p-6 neon-border text-center">
        <AlertCircle className="w-12 h-12 mx-auto text-muted-foreground mb-3" />
        <p className="text-muted-foreground">No result yet. Upload or capture a biometric.</p>
      </Card>
    )
  }

  return (
    <Card className="glassmorphism p-6 neon-border space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Match Result</h3>
        {result.matched || result.access_granted ? (
          <Badge className="bg-green-500/20 text-green-300 border-green-500/50 gap-1">
            <CheckCircle2 className="w-3 h-3" />
            Success
          </Badge>
        ) : (
          <Badge variant="destructive" className="gap-1">
            <AlertCircle className="w-3 h-3" />
            No Match
          </Badge>
        )}
      </div>

      {result.person_id && (
        <div className="relative aspect-video rounded-lg overflow-hidden bg-muted/20 border border-border flex items-center justify-center">
          <Image
            src={`${API_ENDPOINTS.personFaceImage(result.person_id)}`}
            alt={result.full_name || "Person"}
            fill
            className="object-cover"
            onError={(e) => {
              e.currentTarget.style.display = "none"
              const fallback = e.currentTarget.nextElementSibling as HTMLElement
              if (fallback) fallback.style.display = "flex"
            }}
          />
          <div className="hidden flex-col items-center justify-center w-full h-full">
            <User className="w-12 h-12 text-muted-foreground mb-2" />
            <span className="text-sm text-muted-foreground">Image unavailable</span>
          </div>
        </div>
      )}

      <div className="grid gap-3">
        {result.full_name && (
          <div className="flex justify-between items-center py-2 border-b border-border/50">
            <span className="text-muted-foreground">Full Name</span>
            <span className="font-medium">{result.full_name}</span>
          </div>
        )}
        {result.person_id && (
          <div className="flex justify-between items-center py-2 border-b border-border/50">
            <span className="text-muted-foreground">Person ID</span>
            <span className="font-mono text-sm">{result.person_id}</span>
          </div>
        )}
        {result.similarity !== undefined && (
          <div className="flex justify-between items-center py-2 border-b border-border/50">
            <span className="text-muted-foreground">Similarity</span>
            <span className="font-medium">{(result.similarity * 100).toFixed(1)}%</span>
          </div>
        )}
        {result.threshold !== undefined && (
          <div className="flex justify-between items-center py-2 border-b border-border/50">
            <span className="text-muted-foreground">Threshold</span>
            <span className="font-medium">{(result.threshold * 100).toFixed(1)}%</span>
          </div>
        )}
        {result.decision_rule && (
          <div className="flex justify-between items-center py-2">
            <span className="text-muted-foreground">Decision Rule</span>
            <span className="text-sm">{result.decision_rule}</span>
          </div>
        )}
      </div>
    </Card>
  )
}

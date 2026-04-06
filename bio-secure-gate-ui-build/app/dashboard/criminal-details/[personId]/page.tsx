"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  AlertCircle,
  Loader2,
  ShieldCheck,
  ArrowLeft,
  User,
  Mail,
  Phone,
  MapPin,
  FileWarning,
  Lock,
} from "lucide-react"
import { verify2faApi, setTempToken, loginApi, getAccessToken, getStoredUser } from "@/lib/auth"
import { getPerson } from "@/lib/api"
import { API_ENDPOINTS } from "@/lib/api-config"

interface PersonDetail {
  person_id: string
  full_name?: string
  email?: string
  mobile_number?: string
  address?: string
  criminal_records?: string
}

type PageStep = "login" | "2fa" | "details"

export default function CriminalDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const personId = params.personId as string

  const [step, setStep] = useState<PageStep>("login")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Login fields
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  // 2FA fields
  const [totpCode, setTotpCode] = useState("")

  // Person data
  const [person, setPerson] = useState<PersonDetail | null>(null)
  const [faceImageUrl, setFaceImageUrl] = useState<string | null>(null)

  // Pre-fill email from stored user
  useEffect(() => {
    const user = getStoredUser()
    if (user?.email) setEmail(user.email)
  }, [])

  const handleLogin = async () => {
    if (!email || !password) {
      setError("Please enter email and password.")
      return
    }
    try {
      setError(null)
      setLoading(true)
      const result = await loginApi(email, password)
      setTempToken(result.temp_token)
      setStep("2fa")
    } catch (e: any) {
      setError(e?.message || "Login failed.")
    } finally {
      setLoading(false)
    }
  }

  const handleVerify2fa = async () => {
    if (!totpCode || totpCode.length !== 6) {
      setError("Please enter a 6-digit code.")
      return
    }
    try {
      setError(null)
      setLoading(true)
      // Verify 2FA — this confirms the officer's identity
      await verify2faApi(totpCode)
      // 2FA passed — fetch full person details from API
      await fetchPersonDetails()
      setStep("details")
    } catch (e: any) {
      setError(e?.message || "2FA verification failed.")
    } finally {
      setLoading(false)
    }
  }

  const fetchPersonDetails = async () => {
    try {
      // Fetch full person details from backend
      const data = await getPerson(personId)
      setPerson({
        person_id: data.person_id || personId,
        full_name: data.full_name,
        email: data.email,
        mobile_number: data.mobile_number,
        address: data.address,
        criminal_records: data.criminal_records,
      })
      // Load face image
      const token = getAccessToken()
      if (token) {
        setFaceImageUrl(`${API_ENDPOINTS.personFaceImage(data.person_id || personId)}?token=${token}`)
      }
    } catch {
      // If API fails (e.g. 403), fall back to sessionStorage match data
      const raw = sessionStorage.getItem(`criminal_details_${personId}`)
      if (!raw) {
        setError("Could not load person details. Please go back to the match page and try again.")
        return
      }
      try {
        const data = JSON.parse(raw)
        setPerson({
          person_id: data.person_id || personId,
          full_name: data.full_name,
          email: data.email,
          mobile_number: data.mobile_number,
          address: data.address,
          criminal_records: data.criminal_records,
        })
        const token = getAccessToken()
        if (token) {
          setFaceImageUrl(`${API_ENDPOINTS.personFaceImage(data.person_id || personId)}?token=${token}`)
        }
      } catch {
        setError("Failed to load person details.")
      }
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
        <h1 className="text-2xl font-bold tracking-tight">Criminal Details</h1>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Step 1: Officer re-authentication — Login */}
      {step === "login" && (
        <Card className="p-6 space-y-5 bg-card/50 border-border">
          <div className="flex items-center gap-3 text-amber-600">
            <Lock className="w-6 h-6" />
            <div>
              <h2 className="text-lg font-semibold">Authentication Required</h2>
              <p className="text-sm text-muted-foreground">
                Criminal records are sensitive. Please re-authenticate to view details for person <span className="font-mono font-semibold">{personId}</span>.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">Email</label>
              <Input
                type="email"
                placeholder="officer@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Password</label>
              <Input
                type="password"
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              />
            </div>
          </div>

          <Button onClick={handleLogin} disabled={loading} className="w-full">
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Verifying...
              </>
            ) : (
              <>
                <ShieldCheck className="mr-2 h-4 w-4" />
                Continue
              </>
            )}
          </Button>
        </Card>
      )}

      {/* Step 2: 2FA verification */}
      {step === "2fa" && (
        <Card className="p-6 space-y-5 bg-card/50 border-border">
          <div className="flex items-center gap-3 text-amber-600">
            <ShieldCheck className="w-6 h-6" />
            <div>
              <h2 className="text-lg font-semibold">Two-Factor Authentication</h2>
              <p className="text-sm text-muted-foreground">
                Enter the 6-digit code from your authenticator app.
              </p>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">TOTP Code</label>
            <Input
              type="text"
              inputMode="numeric"
              maxLength={6}
              placeholder="000000"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              onKeyDown={(e) => e.key === "Enter" && handleVerify2fa()}
              className="text-center text-2xl tracking-[0.5em] font-mono"
            />
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => { setStep("login"); setTotpCode(""); setError(null) }} className="flex-1">
              Back
            </Button>
            <Button onClick={handleVerify2fa} disabled={loading} className="flex-1">
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Verifying...
                </>
              ) : (
                <>
                  <ShieldCheck className="mr-2 h-4 w-4" />
                  Verify & View Details
                </>
              )}
            </Button>
          </div>
        </Card>
      )}

      {/* Step 3: Person details */}
      {step === "details" && person && (
        <Card className="p-6 space-y-6 bg-card/50 border-border">
          {/* Header with face image */}
          <div className="flex items-start gap-5">
            {faceImageUrl ? (
              <div className="w-32 h-32 rounded-lg overflow-hidden border-2 border-accent/50 shrink-0 bg-black/20">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={faceImageUrl}
                  alt="Enrolled face"
                  className="w-full h-full object-cover"
                  onError={() => setFaceImageUrl(null)}
                />
              </div>
            ) : (
              <div className="w-32 h-32 rounded-lg border-2 border-dashed border-border flex items-center justify-center shrink-0 bg-muted/20">
                <User className="w-10 h-10 text-muted-foreground" />
              </div>
            )}

            <div className="space-y-2 min-w-0">
              <h2 className="text-xl font-bold tracking-tight break-words">{person.full_name || "Unknown"}</h2>
              <div className="font-mono text-sm text-muted-foreground">ID: {person.person_id}</div>
            </div>
          </div>

          {/* Personal information */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Personal Information</h3>
            <div className="grid gap-3">
              {person.email && (
                <div className="flex items-center gap-3 text-sm">
                  <Mail className="w-4 h-4 text-muted-foreground shrink-0" />
                  <span>{person.email}</span>
                </div>
              )}
              {person.mobile_number && (
                <div className="flex items-center gap-3 text-sm">
                  <Phone className="w-4 h-4 text-muted-foreground shrink-0" />
                  <span>{person.mobile_number}</span>
                </div>
              )}
              {person.address && (
                <div className="flex items-center gap-3 text-sm">
                  <MapPin className="w-4 h-4 text-muted-foreground shrink-0" />
                  <span>{person.address}</span>
                </div>
              )}
              {!person.email && !person.mobile_number && !person.address && (
                <div className="text-sm text-muted-foreground italic">No contact information available.</div>
              )}
            </div>
          </div>

          {/* Criminal records */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-2">
              <FileWarning className="w-4 h-4 text-red-500" />
              Criminal Records
            </h3>
            {person.criminal_records && person.criminal_records.trim() !== "" ? (
              <div className="p-4 rounded-lg border border-red-500/30 bg-red-500/5">
                <p className="text-sm text-red-600 dark:text-red-400 whitespace-pre-wrap">{person.criminal_records}</p>
              </div>
            ) : (
              <div className="p-4 rounded-lg border border-green-500/30 bg-green-500/5">
                <p className="text-sm text-green-600 dark:text-green-400">No criminal records found.</p>
              </div>
            )}
          </div>

          <Button variant="outline" className="w-full" onClick={() => router.back()}>
            <ArrowLeft className="mr-2 w-4 h-4" />
            Back to Match
          </Button>
        </Card>
      )}
    </div>
  )
}

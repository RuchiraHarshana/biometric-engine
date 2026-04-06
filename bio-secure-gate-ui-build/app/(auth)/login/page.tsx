"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"

import { AlertCircle, Loader2, Lock, QrCode, ShieldCheck } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"

import {
  loginApi,
  setup2faApi,
  verify2faApi,
  setTempToken,
  setAuthTokens,
  fetchMe,
  setAccessType,
} from "@/lib/auth"

const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
})

type LoginInput = z.infer<typeof loginSchema>

type AuthStep = "credentials" | "2fa-setup" | "2fa-verify"

export default function LoginPage() {
  const [error, setError] = useState<string | null>(null)
  const [step, setStep] = useState<AuthStep>("credentials")
  const [loading, setLoading] = useState(false)

  // 2FA state
  const [otpauthUri, setOtpauthUri] = useState<string | null>(null)
  const [totpSecret, setTotpSecret] = useState<string | null>(null)
  const [totpCode, setTotpCode] = useState("")

  const router = useRouter()

  const form = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  })

  const handleLogin = async (data: LoginInput) => {
    try {
      setError(null)
      const result = await loginApi(data.email, data.password)
      setTempToken(result.temp_token)

      if (result.requires_2fa_setup) {
        // First time — need to show QR code
        try {
          const setupResult = await setup2faApi()
          setOtpauthUri(setupResult.otpauth_uri)
          setTotpSecret(setupResult.secret)
          setStep("2fa-setup")
        } catch (err: any) {
          setError(err.message || "Failed to setup 2FA")
        }
      } else {
        setStep("2fa-verify")
      }
    } catch (err: any) {
      setError(err.message || "Failed to login. Please try again.")
    }
  }

  const handleVerify2fa = async () => {
    if (!totpCode || totpCode.length !== 6) {
      setError("Please enter a 6-digit code")
      return
    }

    try {
      setError(null)
      setLoading(true)
      const result = await verify2faApi(totpCode)
      console.log("[BioSecure] 2FA verify response:", JSON.stringify(result))
      setAuthTokens(result)

      // If access_type wasn't in the verify response, try fetching it
      if (!result.access_type) {
        try {
          const me = await fetchMe()
          console.log("[BioSecure] /me after login:", JSON.stringify(me))
          const at = me.officer?.access_type || me.access_type
          if (at) {
            setAccessType(at)
          }
        } catch {
          // Non-critical — continue
        }
      }

      router.push("/dashboard")
    } catch (err: any) {
      setError(err.message || "Invalid 2FA code")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <header className="border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link href="/">
            <div className="flex items-center gap-2 hover:opacity-80 transition-opacity">
              <div className="w-8 h-8 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center">
                <Lock className="w-5 h-5 text-accent" />
              </div>
              <span className="font-semibold text-lg">BioSecureGate</span>
            </div>
          </Link>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-4 py-12">
        <Card className="w-full max-w-md bg-card/50 border-border">
          <div className="p-8">
            <div className="flex items-center justify-center mb-8">
              <div className="w-10 h-10 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center">
                {step === "credentials" ? (
                  <Lock className="w-6 h-6 text-accent" />
                ) : step === "2fa-setup" ? (
                  <QrCode className="w-6 h-6 text-accent" />
                ) : (
                  <ShieldCheck className="w-6 h-6 text-accent" />
                )}
              </div>
            </div>

            <div className="space-y-2 mb-6 text-center">
              <h1 className="text-2xl font-bold">
                {step === "credentials"
                  ? "Login"
                  : step === "2fa-setup"
                    ? "Setup Authenticator"
                    : "Enter 2FA Code"}
              </h1>
              <p className="text-sm text-muted-foreground">
                {step === "credentials"
                  ? "Sign in with your credentials"
                  : step === "2fa-setup"
                    ? "Scan the QR code with your authenticator app, then enter the code below"
                    : "Enter the 6-digit code from your authenticator app"}
              </p>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* STEP 1: Credentials */}
            {step === "credentials" && (
              <form onSubmit={form.handleSubmit(handleLogin)} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Email</label>
                  <Input
                    type="email"
                    placeholder="you@example.com"
                    {...form.register("email")}
                    className="bg-input border-border"
                  />
                  {form.formState.errors.email && (
                    <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Password</label>
                  <Input
                    type="password"
                    placeholder="••••••"
                    {...form.register("password")}
                    className="bg-input border-border"
                  />
                  {form.formState.errors.password && (
                    <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>
                  )}
                </div>

                <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
                  {form.formState.isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Logging in...
                    </>
                  ) : (
                    "Login"
                  )}
                </Button>
              </form>
            )}

            {/* STEP 2a: 2FA Setup (QR code) */}
            {step === "2fa-setup" && (
              <div className="space-y-4">
                {otpauthUri && (
                  <div className="flex flex-col items-center gap-3">
                    <div className="bg-white p-4 rounded-lg">
                      {/* QR code rendered via a simple img from Google Charts API */}
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(otpauthUri)}`}
                        alt="2FA QR Code"
                        width={200}
                        height={200}
                      />
                    </div>
                    {totpSecret && (
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground mb-1">Or enter this secret manually:</p>
                        <code className="text-xs bg-secondary/50 px-3 py-1.5 rounded select-all break-all">
                          {totpSecret}
                        </code>
                      </div>
                    )}
                  </div>
                )}

                <div className="space-y-2">
                  <label className="text-sm font-medium">Verification Code</label>
                  <Input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="123456"
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    className="bg-input border-border text-center text-xl tracking-widest"
                  />
                </div>

                <Button onClick={handleVerify2fa} className="w-full" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Verifying...
                    </>
                  ) : (
                    "Verify & Login"
                  )}
                </Button>
              </div>
            )}

            {/* STEP 2b: 2FA Verify (returning user) */}
            {step === "2fa-verify" && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Authenticator Code</label>
                  <Input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="123456"
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    className="bg-input border-border text-center text-xl tracking-widest"
                    autoFocus
                  />
                </div>

                <Button onClick={handleVerify2fa} className="w-full" disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Verifying...
                    </>
                  ) : (
                    "Verify & Login"
                  )}
                </Button>

                <Button
                  variant="ghost"
                  className="w-full text-sm text-muted-foreground"
                  onClick={() => {
                    setStep("credentials")
                    setTotpCode("")
                    setError(null)
                  }}
                >
                  Back to login
                </Button>
              </div>
            )}
          </div>
        </Card>
      </main>
    </div>
  )
}

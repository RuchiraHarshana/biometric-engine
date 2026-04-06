"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle, Loader2, Lock, Sparkles, QrCode, ShieldCheck } from "lucide-react"
import { useForm } from "react-hook-form"
import { z } from "zod"
import { zodResolver } from "@hookform/resolvers/zod"
import {
  loginApi,
  setup2faApi,
  verify2faApi,
  setTempToken,
  setAuthTokens,
} from "@/lib/auth"

const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
})

type LoginInput = z.infer<typeof loginSchema>
type AuthStep = "credentials" | "2fa-setup" | "2fa-verify"

export function LoginForm() {
  const [error, setError] = useState<string | null>(null)
  const [step, setStep] = useState<AuthStep>("credentials")
  const [loading, setLoading] = useState(false)
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
      setAuthTokens(result)

      // Fetch and store access_type
      const { refreshAccessType } = await import("@/lib/auth")
      await refreshAccessType()

      router.push("/dashboard")
    } catch (err: any) {
      setError(err.message || "Invalid 2FA code")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-md glassmorphism neon-border">
      <div className="p-8">
        <div className="flex items-center justify-center mb-8">
          <div className="w-10 h-10 rounded-lg glassmorphism border border-accent/50 flex items-center justify-center shadow-lg shadow-accent/20">
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
          <div className="flex items-center justify-center gap-2 mb-4">
            <Sparkles className="w-4 h-4 text-accent" />
            <h1 className="text-2xl font-bold">BioSecureGate</h1>
          </div>
          <p className="text-sm text-muted-foreground">
            {step === "credentials"
              ? "Sign in with your credentials"
              : step === "2fa-setup"
                ? "Scan QR code with your authenticator app"
                : "Enter the 6-digit code from your authenticator"}
          </p>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-6 glassmorphism border-destructive/50">
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
                className="glassmorphism bg-input/50 border-accent/30"
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
                className="glassmorphism bg-input/50 border-accent/30"
              />
              {form.formState.errors.password && (
                <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full bg-accent hover:bg-accent/90 text-accent-foreground shadow-lg shadow-accent/30"
              disabled={form.formState.isSubmitting}
            >
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

        {/* STEP 2a: 2FA Setup */}
        {step === "2fa-setup" && (
          <div className="space-y-4">
            {otpauthUri && (
              <div className="flex flex-col items-center gap-3">
                <div className="bg-white p-4 rounded-lg">
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
                    <p className="text-xs text-muted-foreground mb-1">Manual entry:</p>
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
                className="glassmorphism bg-input/50 border-accent/30 text-center text-xl tracking-widest"
              />
            </div>

            <Button
              onClick={handleVerify2fa}
              className="w-full bg-accent hover:bg-accent/90 text-accent-foreground"
              disabled={loading}
            >
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

        {/* STEP 2b: 2FA Verify */}
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
                className="glassmorphism bg-input/50 border-accent/30 text-center text-xl tracking-widest"
                autoFocus
              />
            </div>

            <Button
              onClick={handleVerify2fa}
              className="w-full bg-accent hover:bg-accent/90 text-accent-foreground"
              disabled={loading}
            >
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
  )
}

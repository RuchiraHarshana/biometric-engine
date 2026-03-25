"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Fingerprint, Fence as Face, CheckCircle2, Zap, Lock, AlertCircle, Sparkles } from "lucide-react"
import { API_ENDPOINTS } from "@/lib/api-config"
import { ThemeToggle } from "@/components/theme-toggle"

export default function Landing() {
  const [backendStatus, setBackendStatus] = useState<"connected" | "disconnected">("disconnected")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()

    const checkHealth = async () => {
      try {
        const response = await fetch(API_ENDPOINTS.health, {
          method: "GET",
          signal: controller.signal,
          cache: "no-store",
        })
        setBackendStatus(response.ok ? "connected" : "disconnected")
      } catch {
        setBackendStatus("disconnected")
      } finally {
        setLoading(false)
      }
    }

    checkHealth()
    return () => controller.abort()
  }, [])

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      {/* Header */}
      <header className="border-b border-border/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg glassmorphism border-accent/50 flex items-center justify-center shadow-lg shadow-accent/20">
              <Lock className="w-5 h-5 text-accent" />
            </div>
            <span className="font-semibold text-lg font-mono">BioSecureGate</span>
          </div>
          <ThemeToggle />
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        {/* Hero Section */}
        <section className="border-b border-border/50 relative overflow-hidden">
          <div className="absolute inset-0 overflow-hidden">
            <div className="absolute top-0 left-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl" />
            <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl" />
          </div>

          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20 sm:py-32 relative">
            <div className="space-y-8">
              <div className="space-y-4">
                <div className="inline-flex items-center gap-2 glassmorphism px-4 py-2 rounded-full border border-accent/30 w-fit">
                  <Sparkles className="w-4 h-4 text-accent" />
                  <span className="text-sm font-medium text-accent">Biometric Security Platform</span>
                </div>

                <h1 className="text-5xl sm:text-6xl font-bold tracking-tight bg-gradient-to-r from-foreground to-muted-foreground bg-clip-text text-transparent">
                  BioSecureGate
                </h1>

                <p className="text-xl text-muted-foreground max-w-2xl">
                  Advanced face & fingerprint verification powered by FastAPI
                </p>
              </div>

              {/* CTA Buttons */}
              <div className="flex flex-wrap gap-4 pt-4">
                {/* ✅ FIX: route groups are NOT part of the URL */}
                <Link href="/login">
                  <Button
                    size="lg"
                    className="gap-2 bg-accent hover:bg-accent/90 text-accent-foreground shadow-lg shadow-accent/30"
                  >
                    <Lock className="w-4 h-4" />
                    Login to System
                  </Button>
                </Link>

                <Link href="/login">
                  <Button
                    size="lg"
                    variant="outline"
                    className="gap-2 glassmorphism bg-transparent border-accent/50 hover:bg-accent/5"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Get Started
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        </section>

        {/* System Status Widget */}
        <section className="border-b border-border/50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground mb-4">
              System Status
            </h2>

            <Card className="glassmorphism neon-border p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {loading ? (
                    <div className="w-3 h-3 rounded-full bg-muted animate-pulse" />
                  ) : backendStatus === "connected" ? (
                    <div className="w-3 h-3 rounded-full bg-green-500 shadow-lg shadow-green-500/50" />
                  ) : (
                    <div className="w-3 h-3 rounded-full bg-red-500 shadow-lg shadow-red-500/50" />
                  )}
                  <span className="text-sm font-medium">Backend API</span>
                </div>

                <Badge
                  variant={backendStatus === "connected" ? "default" : "destructive"}
                  className={
                    backendStatus === "connected"
                      ? "bg-green-500/20 text-green-300 border-green-500/50 gap-1"
                      : "gap-1"
                  }
                >
                  {backendStatus === "connected" ? (
                    <>
                      <CheckCircle2 className="w-3 h-3" />
                      Connected
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-3 h-3" />
                      Disconnected
                    </>
                  )}
                </Badge>
              </div>
            </Card>

            {backendStatus === "disconnected" && (
              <Alert variant="destructive" className="mt-4 glassmorphism border-destructive/50">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  Backend API is not accessible. Ensure FastAPI server is running at http://127.0.0.1:8000
                </AlertDescription>
              </Alert>
            )}
          </div>
        </section>

        {/* Features Grid */}
        <section className="py-20 sm:py-28">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12 space-y-4">
              <h2 className="text-3xl sm:text-4xl font-bold">Core Features</h2>
              <p className="text-muted-foreground max-w-2xl mx-auto">
                Enterprise-grade biometric verification with advanced AI matching
              </p>
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              <Card className="glassmorphism neon-border p-6 hover:shadow-lg hover:shadow-accent/20 transition-all">
                <div className="w-10 h-10 rounded-lg glassmorphism border border-accent/50 flex items-center justify-center mb-4 shadow-lg shadow-accent/20">
                  <Face className="w-6 h-6 text-accent" />
                </div>
                <h3 className="text-lg font-semibold mb-2">Face Recognition</h3>
                <p className="text-sm text-muted-foreground">
                  Advanced facial recognition for secure identity verification and enrollment
                </p>
              </Card>

              <Card className="glassmorphism neon-border p-6 hover:shadow-lg hover:shadow-accent/20 transition-all">
                <div className="w-10 h-10 rounded-lg glassmorphism border border-accent/50 flex items-center justify-center mb-4 shadow-lg shadow-accent/20">
                  <Fingerprint className="w-6 h-6 text-accent" />
                </div>
                <h3 className="text-lg font-semibold mb-2">Fingerprint Matching</h3>
                <p className="text-sm text-muted-foreground">
                  Precise biometric fingerprint matching for authentication
                </p>
              </Card>

              <Card className="glassmorphism neon-border p-6 hover:shadow-lg hover:shadow-accent/20 transition-all">
                <div className="w-10 h-10 rounded-lg glassmorphism border border-accent/50 flex items-center justify-center mb-4 shadow-lg shadow-accent/20">
                  <Zap className="w-6 h-6 text-accent" />
                </div>
                <h3 className="text-lg font-semibold mb-2">2FA Verification</h3>
                <p className="text-sm text-muted-foreground">
                  Multi-factor biometric verification for maximum security
                </p>
              </Card>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/50 bg-card/20 backdrop-blur-sm py-8 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <p>BioSecureGate v2.0.0</p>
            <a href="#" target="_blank" rel="noopener noreferrer" className="hover:text-accent transition-colors">
              Sci-Fi Enterprise System
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}

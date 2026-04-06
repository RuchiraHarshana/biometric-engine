"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { canEnroll } from "@/lib/auth"
import { EnrollForm } from "@/components/enroll-form"

export default function EnrollPage() {
  const router = useRouter()

  useEffect(() => {
    if (!canEnroll()) {
      router.push("/dashboard")
    }
  }, [router])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      <div className="space-y-4 mb-6">
        <h1 className="text-3xl font-bold">Register Criminal</h1>
        <p className="text-muted-foreground">Enroll face or fingerprint biometric data for persons</p>
      </div>
      <EnrollForm />
    </div>
  )
}

"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function VerifyPage() {
  const router = useRouter()

  useEffect(() => {
    router.replace("/dashboard/combined-verify")
  }, [router])

  return null
}

"use client"

import { Button } from "@/components/ui/button"
import { CheckCircle2 } from "lucide-react"
import Link from "next/link"

export default function EnrollSuccessPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      <div className="space-y-6 max-w-md w-full bg-card/50 border border-border rounded-lg p-8 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12 text-green-500" />
        <h1 className="text-2xl font-bold">Enrollment Successful!</h1>
        <p className="text-muted-foreground">The person has been enrolled successfully. You can now return to the dashboard or enroll another person.</p>
        <div className="flex flex-col gap-2 mt-4">
          <Link href="/dashboard">
            <Button className="w-full">Go to Dashboard</Button>
          </Link>
          <Link href="/dashboard/enroll">
            <Button variant="outline" className="w-full">Enroll Another</Button>
          </Link>
        </div>
      </div>
    </div>
  )
}

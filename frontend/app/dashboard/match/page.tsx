import { MatchForm } from "@/components/match-form"

export default function MatchPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6">
      <div className="space-y-4 mb-6">
        <h1 className="text-3xl font-bold">Biometric Matching</h1>
        <p className="text-muted-foreground">Match biometric data against enrolled profiles</p>
      </div>
      <MatchForm />
    </div>
  )
}

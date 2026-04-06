"use client"

import { useEffect, useState } from "react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle, Users, Activity, Zap, Upload, ShieldCheck } from "lucide-react"
import { getPersons } from "@/lib/api"
import { isAdmin, getStoredUser, refreshAccessType } from "@/lib/auth"
import { SkeletonCard } from "@/components/skeleton-card"

interface Person {
  person_id: string
  full_name: string
  has_face: boolean
  has_fingerprint: boolean
}

interface DashboardStats {
  totalPersons: number
  faceEnrolled: number
  fingerprintEnrolled: number
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [persons, setPersons] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [user, setUser] = useState<ReturnType<typeof getStoredUser>>(null)

  useEffect(() => {
    setUser(getStoredUser())

    // Refresh access_type from backend for officers
    if (!isAdmin()) {
      refreshAccessType().then(() => {
        setUser(getStoredUser())
      })
    }

    const fetchData = async () => {
      try {
        setLoading(true)
        setError(null)

        // Only admins can list persons; officers see limited stats
        if (!isAdmin()) {
          setStats({ totalPersons: 0, faceEnrolled: 0, fingerprintEnrolled: 0 })
          setLoading(false)
          return
        }

        const data = await getPersons()

        if (Array.isArray(data)) {
          setPersons(data)
          const faceCount = data.filter((p: Person) => p.has_face).length
          const fingerprintCount = data.filter((p: Person) => p.has_fingerprint).length

          setStats({
            totalPersons: data.length,
            faceEnrolled: faceCount,
            fingerprintEnrolled: fingerprintCount,
          })
        }
      } catch (err) {
        setError("Failed to fetch dashboard data. Please ensure the backend is running.")
        setStats({
          totalPersons: 0,
          faceEnrolled: 0,
          fingerprintEnrolled: 0,
        })
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [])

  return (
    <div className="p-6 space-y-6">
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Officer Permissions */}
      {user && user.role === "officer" && (
        <Card className="bg-card/50 border-border p-6">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck className="w-5 h-5 text-accent" />
            <h2 className="text-lg font-semibold">Your Permissions</h2>
          </div>
          <div className="flex flex-wrap gap-3">
            <div className="flex items-center gap-2 px-4 py-3 rounded-lg border border-blue-500/30 bg-blue-500/10">
              <Zap className="w-5 h-5 text-blue-500" />
              <div>
                <p className="text-sm font-medium text-blue-500">Match Access</p>
                <p className="text-xs text-muted-foreground">Search and match biometric data</p>
              </div>
            </div>
            {user.accessType === "register_and_verify" && (
              <div className="flex items-center gap-2 px-4 py-3 rounded-lg border border-green-500/30 bg-green-500/10">
                <Upload className="w-5 h-5 text-green-500" />
                <div>
                  <p className="text-sm font-medium text-green-500">Enroll Access</p>
                  <p className="text-xs text-muted-foreground">Register new persons and biometrics</p>
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid md:grid-cols-3 gap-6">
        {loading ? (
          <>
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </>
        ) : stats ? (
          <>
            <Card className="bg-card/50 border-border p-6">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">Total Persons</p>
                  <p className="text-3xl font-bold">{stats.totalPersons}</p>
                </div>
                <div className="w-10 h-10 rounded-lg bg-accent/20 border border-accent/30 flex items-center justify-center">
                  <Users className="w-5 h-5 text-accent" />
                </div>
              </div>
            </Card>

            <Card className="bg-card/50 border-border p-6">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">Face Enrolled</p>
                  <p className="text-3xl font-bold">{stats.faceEnrolled}</p>
                </div>
                <Badge variant="secondary">
                  {Math.round((stats.faceEnrolled / Math.max(stats.totalPersons, 1)) * 100)}%
                </Badge>
              </div>
            </Card>

            <Card className="bg-card/50 border-border p-6">
              <div className="flex items-start justify-between">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">Fingerprint Enrolled</p>
                  <p className="text-3xl font-bold">{stats.fingerprintEnrolled}</p>
                </div>
                <Badge variant="secondary">
                  {Math.round((stats.fingerprintEnrolled / Math.max(stats.totalPersons, 1)) * 100)}%
                </Badge>
              </div>
            </Card>
          </>
        ) : null}
      </div>

      {/* Recent Activity */}
      <Card className="bg-card/50 border-border p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-5 h-5 text-accent" />
          <h2 className="text-lg font-semibold">Recent Persons</h2>
        </div>
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-muted rounded animate-pulse" />
            ))}
          </div>
        ) : persons.length > 0 ? (
          <div className="space-y-2">
            {persons.slice(0, 5).map((person) => (
              <div
                key={person.person_id}
                className="flex items-center justify-between p-3 rounded-lg border border-border bg-background/50"
              >
                <div>
                  <p className="font-medium">{person.full_name}</p>
                  <p className="text-xs text-muted-foreground">{person.person_id}</p>
                </div>
                <div className="flex gap-2">
                  {person.has_face && <Badge variant="outline">Face</Badge>}
                  {person.has_fingerprint && <Badge variant="outline">Fingerprint</Badge>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-8">No persons enrolled yet</p>
        )}
      </Card>
    </div>
  )
}

"use client"

import { useEffect, useState } from "react"
import { getStoredUser, type AuthUser } from "@/lib/auth"
import { ThemeToggle } from "@/components/theme-toggle"
import { Badge } from "@/components/ui/badge"

export function DashboardHeader() {
  const [user, setUser] = useState<AuthUser | null>(null)

  useEffect(() => {
    setUser(getStoredUser())
  }, [])

  return (
    <header className="glassmorphism border-b border-border/50 px-6 py-4 sticky top-0 z-30">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Dashboard</h1>
          {user && (
            <div className="flex items-center gap-3 mt-2">
              <p className="text-sm text-muted-foreground">{user.email}</p>
              {user.role === "admin" && (
                <Badge className="bg-accent/20 text-accent border-accent/50">Admin</Badge>
              )}
              {user.role === "officer" && (
                <Badge variant="outline" className="text-xs">
                  {user.accessType === "register_and_verify" ? "Register & Verify" : "Verify Only"}
                </Badge>
              )}
            </div>
          )}
        </div>
        <ThemeToggle />
      </div>
    </header>
  )
}

"use client"

import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Lock, BarChart3, Upload, Zap, ShieldCheck, LogOut, Sparkles, Users, UserCog } from "lucide-react"
import { clearAuth, isAdmin, canEnroll, refreshAccessType } from "@/lib/auth"
import { useEffect, useState } from "react"

export function DashboardNav() {
  const pathname = usePathname()
  const router = useRouter()
  const [adminUser, setAdminUser] = useState(false)
  const [enrollAccess, setEnrollAccess] = useState(false)

  useEffect(() => {
    setAdminUser(isAdmin())
    setEnrollAccess(canEnroll())

    // If officer, refresh access_type from backend in case it was not stored during login
    if (!isAdmin()) {
      refreshAccessType().then(() => {
        setEnrollAccess(canEnroll())
      })
    }
  }, [])

  const handleLogout = () => {
    clearAuth()
    router.push("/")
  }

  const navItems = [
    { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
    ...(adminUser ? [{ href: "/dashboard/admin", label: "Officers", icon: UserCog }] : []),
    ...(adminUser ? [{ href: "/dashboard/persons", label: "Persons", icon: Users }] : []),
    ...(enrollAccess ? [{ href: "/dashboard/enroll", label: "Enroll", icon: Upload }] : []),
    { href: "/dashboard/match", label: "Match", icon: Zap },
    { href: "/dashboard/verify", label: "Combined Verify", icon: ShieldCheck },
  ]

  return (
    <aside className="w-64 glassmorphism border-r border-border/50 flex flex-col h-screen">
      <div className="p-6 border-b border-border/50">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg glassmorphism border border-accent/50 flex items-center justify-center shadow-lg shadow-accent/20">
            <Lock className="w-5 h-5 text-accent" />
          </div>
          <div>
            <span className="font-semibold text-lg font-mono">BioSecure</span>
            {adminUser && <p className="text-xs text-accent mt-1 font-medium">🔒 Admin Mode</p>}
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href
          const Icon = item.icon
          return (
            <Link key={item.href} href={item.href}>
              <Button
                variant={isActive ? "default" : "ghost"}
                className={`w-full justify-start gap-2 ${
                  isActive ? "bg-accent/20 text-accent border border-accent/50" : "hover:bg-accent/10"
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </Button>
            </Link>
          )
        })}
      </nav>

      <div className="p-4 border-t border-border/50 space-y-2">
        <div className="text-xs text-muted-foreground glassmorphism p-3 rounded border border-accent/20 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-accent" />
          <span>Sci-Fi Interface v2.0</span>
        </div>
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 text-destructive hover:text-destructive hover:bg-destructive/10"
          onClick={handleLogout}
        >
          <LogOut className="w-4 h-4" />
          Logout
        </Button>
      </div>
    </aside>
  )
}

import { API_ENDPOINTS } from "./api-config"

// --- Storage keys ---
const ACCESS_TOKEN_KEY = "access_token"
const TEMP_TOKEN_KEY = "temp_token"
const USER_ROLE_KEY = "user_role"
const USER_EMAIL_KEY = "user_email"
const USER_ACCESS_TYPE_KEY = "user_access_type"

// --- Types ---
export type UserRole = "admin" | "officer"
export type AccessType = "register_and_verify" | "verify_only"

export interface AuthUser {
  email: string
  role: UserRole
  accessType?: AccessType
}

// --- Token helpers ---
export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getTempToken(): string | null {
  if (typeof window === "undefined") return null
  return localStorage.getItem(TEMP_TOKEN_KEY)
}

export function setTempToken(token: string) {
  if (typeof window === "undefined") return
  localStorage.setItem(TEMP_TOKEN_KEY, token)
}

export function clearTempToken() {
  if (typeof window === "undefined") return
  localStorage.removeItem(TEMP_TOKEN_KEY)
}

export function setAuthTokens(data: { access_token: string; role: string; email: string; access_type?: string }) {
  if (typeof window === "undefined") return
  localStorage.setItem(ACCESS_TOKEN_KEY, data.access_token)
  localStorage.setItem(USER_ROLE_KEY, data.role)
  localStorage.setItem(USER_EMAIL_KEY, data.email)
  localStorage.removeItem(TEMP_TOKEN_KEY)
  if (data.access_type) {
    localStorage.setItem(USER_ACCESS_TYPE_KEY, data.access_type)
    console.log("[BioSecure] access_type saved from auth tokens:", data.access_type)
  }
}

export function clearAuth() {
  if (typeof window === "undefined") return
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(TEMP_TOKEN_KEY)
  localStorage.removeItem(USER_ROLE_KEY)
  localStorage.removeItem(USER_EMAIL_KEY)
  localStorage.removeItem(USER_ACCESS_TYPE_KEY)
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null
  const email = localStorage.getItem(USER_EMAIL_KEY)
  const role = localStorage.getItem(USER_ROLE_KEY) as UserRole | null
  if (!email || !role) return null
  const accessType = localStorage.getItem(USER_ACCESS_TYPE_KEY) as AccessType | null
  return { email, role, accessType: accessType ?? undefined }
}

export function setAccessType(accessType: AccessType) {
  if (typeof window === "undefined") return
  localStorage.setItem(USER_ACCESS_TYPE_KEY, accessType)
}

export function isAuthenticated(): boolean {
  return !!getAccessToken()
}

export function isAdmin(): boolean {
  if (typeof window === "undefined") return false
  return localStorage.getItem(USER_ROLE_KEY) === "admin"
}

export function canEnroll(): boolean {
  if (typeof window === "undefined") return false
  const role = localStorage.getItem(USER_ROLE_KEY)
  if (role === "admin") return true
  const accessType = localStorage.getItem(USER_ACCESS_TYPE_KEY)
  return accessType === "register_and_verify"
}

export function canVerify(): boolean {
  if (typeof window === "undefined") return false
  return !!localStorage.getItem(USER_ROLE_KEY) // all authenticated users
}

// --- Auth header helper ---
export function authHeaders(): Record<string, string> {
  const token = getAccessToken()
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}

export function tempAuthHeaders(): Record<string, string> {
  const token = getTempToken()
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}

// --- API calls ---
export async function loginApi(email: string, password: string) {
  const res = await fetch(API_ENDPOINTS.login, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Login failed" }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json() as Promise<{ temp_token: string; requires_2fa_setup: boolean; message: string }>
}

export async function setup2faApi() {
  const res = await fetch(API_ENDPOINTS.twoFaSetup, {
    method: "POST",
    headers: tempAuthHeaders(),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "2FA setup failed" }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json() as Promise<{ secret: string; otpauth_uri: string; message: string }>
}

export async function verify2faApi(code: string) {
  const res = await fetch(API_ENDPOINTS.twoFaVerify, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...tempAuthHeaders() },
    body: JSON.stringify({ code }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "2FA verification failed" }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json() as Promise<{ access_token: string; token_type: string; role: string; email: string; access_type?: string; [key: string]: any }>
}

export async function fetchMe() {
  const res = await fetch(API_ENDPOINTS.me, {
    method: "GET",
    headers: authHeaders(),
  })
  if (!res.ok) {
    throw new Error("Failed to fetch user info")
  }
  return res.json()
}

// Decode JWT payload without a library
function decodeJwtPayload(token: string): Record<string, any> | null {
  try {
    const parts = token.split(".")
    if (parts.length !== 3) return null
    const payload = parts[1].replace(/-/g, "+").replace(/_/g, "/")
    const decoded = atob(payload)
    return JSON.parse(decoded)
  } catch {
    return null
  }
}

// Check if access_type is already stored from login; if not, try to fetch it from /me
export async function refreshAccessType(): Promise<void> {
  // If already stored in localStorage (set during login), skip network calls
  const existing = typeof window !== "undefined" ? localStorage.getItem("user_access_type") : null
  if (existing) return

  try {
    const me = await fetchMe()
    const accessType =
      me.officer?.access_type ||
      me.access_type ||
      me.user?.access_type
    if (accessType) {
      setAccessType(accessType)
      return
    }

    const token = getAccessToken()
    if (token) {
      const payload = decodeJwtPayload(token)
      const jwtAccessType = payload?.access_type
      if (jwtAccessType) {
        setAccessType(jwtAccessType)
        return
      }
    }
  } catch {
    // Silently fail — access_type must come from login response
  }
}

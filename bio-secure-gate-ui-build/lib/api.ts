// --- Person Update ---
export async function updatePerson(personId: string, updates: Record<string, any>) {
  const token = localStorage.getItem("access_token")
  const res = await fetch(`${API_ENDPOINTS.persons}/${personId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`,
    },
    body: JSON.stringify(updates),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}
import { API_ENDPOINTS } from "@/lib/api-config"
import { authHeaders } from "@/lib/auth"

function stringifyMaybeObject(value: unknown): string {
  if (typeof value === "string") return value
  if (value == null) return ""
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

async function throwApiError(res: Response): Promise<never> {
  const payload = await res.json().catch(() => null as any)
  const detail = payload?.detail ?? payload?.error ?? payload
  const detailText = stringifyMaybeObject(detail)
  const message = detailText || `HTTP ${res.status}`
  throw new Error(message)
}

// --- Generic helpers ---

async function authFetch(url: string, init?: RequestInit) {
  const res = await fetch(url, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
  })
  if (!res.ok) {
    await throwApiError(res)
  }
  return res.json()
}

async function authFormPost(url: string, formData: FormData, timeoutMs = 45000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let res: Response
  try {
    res = await fetch(url, {
      method: "POST",
      headers: authHeaders(),
      body: formData,
      signal: controller.signal,
    })
  } catch (err: any) {
    clearTimeout(timer)
    const msg = err?.name === "AbortError"
      ? "Request timed out while uploading fingerprint image. Try a smaller/clearer image."
      : "Network upload failed (Failed to fetch). Check internet/API availability and try again."
    throw new Error(msg)
  }
  clearTimeout(timer)
  if (!res.ok) {
    await throwApiError(res)
  }
  return res.json()
}

async function normalizeFingerprintFile(file: File): Promise<File> {
  if (!file.type.startsWith("image/")) {
    return file
  }

  try {
    const bitmap = await createImageBitmap(file)
    const maxDim = 1200
    const longest = Math.max(bitmap.width, bitmap.height)
    const scale = longest > maxDim ? maxDim / longest : 1
    const targetW = Math.max(1, Math.round(bitmap.width * scale))
    const targetH = Math.max(1, Math.round(bitmap.height * scale))

    const canvas = document.createElement("canvas")
    canvas.width = targetW
    canvas.height = targetH
    const ctx = canvas.getContext("2d")
    if (!ctx) {
      return file
    }
    ctx.drawImage(bitmap, 0, 0, targetW, targetH)
    bitmap.close()

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob((b) => resolve(b), "image/jpeg", 0.9)
    })
    if (!blob) {
      return file
    }
    return new File([blob], file.name.replace(/\.[^.]+$/, ".jpg"), { type: "image/jpeg" })
  } catch {
    return file
  }
}

// --- Persons ---

export async function getPersons() {
  return authFetch(API_ENDPOINTS.persons)
}

export async function getPerson(personId: string) {
  return authFetch(`${API_ENDPOINTS.persons}/${personId}`)
}

export async function deletePerson(personId: string) {
  return authFetch(`${API_ENDPOINTS.persons}/${personId}`, { method: "DELETE" })
}

// --- Face Enrollment ---

export async function enrollFace(
  personId: string,
  file: File,
  data?: { full_name?: string; email?: string; mobile_number?: string; address?: string; criminal_records?: string },
) {
  const fd = new FormData()
  fd.append("person_id", personId)
  fd.append("image", file)
  if (data) {
    Object.entries(data).forEach(([key, value]) => {
      if (value) fd.append(key, value)
    })
  }
  return authFormPost(API_ENDPOINTS.enrollFace, fd)
}

// --- Fingerprint Enrollment ---

export async function enrollFingerprint(
  personId: string,
  file: File,
  data?: {
    full_name?: string
    email?: string
    mobile_number?: string
    address?: string
    criminal_records?: string
    capture_method?: string
    finger_label?: string
  },
) {
  const normalized = await normalizeFingerprintFile(file)
  const fd = new FormData()
  fd.append("person_id", personId)
  fd.append("image", normalized)
  fd.append("capture_method", data?.capture_method || "image_upload")
  if (data?.finger_label) {
    fd.append("finger_label", data.finger_label)
  }
  if (data) {
    const { capture_method, finger_label, ...rest } = data
    Object.entries(rest).forEach(([key, value]) => {
      if (value) fd.append(key, value)
    })
  }
  // Enrollment should finish quickly; keep a moderate timeout.
  return authFormPost(API_ENDPOINTS.enrollFingerprint, fd, 90000)
}

// --- Face Matching ---

export async function matchFace(file: File) {
  const fd = new FormData()
  fd.append("image", file)
  return authFormPost(API_ENDPOINTS.matchFace, fd)
}

// --- Fingerprint Matching ---

export async function matchFingerprint(file: File, opts?: { capture_method?: string; finger_label?: string }) {
  const normalized = await normalizeFingerprintFile(file)
  const fd = new FormData()
  fd.append("image", normalized)
  if (opts?.capture_method) {
    fd.append("capture_method", opts.capture_method)
  }
  if (opts?.finger_label) {
    fd.append("finger_label", opts.finger_label)
  }
  // Matching can take longer with many stored templates (batched backend matching).
  return authFormPost(API_ENDPOINTS.matchFingerprint, fd, 180000)
}

// --- Combined Verify ---

export async function verify(faceFile?: File, fingerprintFile?: File) {
  const fd = new FormData()
  if (faceFile) fd.append("face_image", faceFile)
  if (fingerprintFile) fd.append("fingerprint_image", fingerprintFile)
  return authFormPost(API_ENDPOINTS.verify, fd)
}

// --- Admin: Officers ---

export interface OfficerOut {
  user_id: string
  email: string
  is_active: boolean
  full_name: string
  rank?: string
  id_number: string
  work_station: string
  access_type: "register_and_verify" | "verify_only"
}

export interface CreateOfficerInput {
  email: string
  password: string
  full_name: string
  rank?: string
  id_number: string
  work_station: string
  access_type: "register_and_verify" | "verify_only"
}

export interface UpdateOfficerInput {
  full_name?: string
  rank?: string
  work_station?: string
  access_type?: "register_and_verify" | "verify_only"
  is_active?: boolean
}

export async function getOfficers(): Promise<OfficerOut[]> {
  return authFetch(API_ENDPOINTS.officers)
}

export async function createOfficer(data: CreateOfficerInput): Promise<OfficerOut> {
  return authFetch(API_ENDPOINTS.officers, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
}

export async function getOfficer(userId: string): Promise<OfficerOut> {
  return authFetch(API_ENDPOINTS.officer(userId))
}

export async function updateOfficer(userId: string, data: UpdateOfficerInput): Promise<OfficerOut> {
  return authFetch(API_ENDPOINTS.officer(userId), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  })
}

export async function deleteOfficer(userId: string) {
  return authFetch(API_ENDPOINTS.officer(userId), { method: "DELETE" })
}

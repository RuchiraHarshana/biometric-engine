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

// --- Generic helpers ---

async function authFetch(url: string, init?: RequestInit) {
  const res = await fetch(url, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

async function authFormPost(url: string, formData: FormData) {
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// --- Persons ---

export async function getPersons() {
  return authFetch(API_ENDPOINTS.persons)
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
  },
) {
  const fd = new FormData()
  fd.append("person_id", personId)
  fd.append("image", file)
  fd.append("capture_method", data?.capture_method || "image_upload")
  if (data) {
    const { capture_method, ...rest } = data
    Object.entries(rest).forEach(([key, value]) => {
      if (value) fd.append(key, value)
    })
  }
  return authFormPost(API_ENDPOINTS.enrollFingerprint, fd)
}

// --- Face Matching ---

export async function matchFace(file: File) {
  const fd = new FormData()
  fd.append("image", file)
  return authFormPost(API_ENDPOINTS.matchFace, fd)
}

// --- Fingerprint Matching ---

export async function matchFingerprint(file: File) {
  const fd = new FormData()
  fd.append("image", file)
  return authFormPost(API_ENDPOINTS.matchFingerprint, fd)
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

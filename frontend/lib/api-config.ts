export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"

export const SCANNER_WS_URL = "ws://127.0.0.1:9100/ws"
export const SCANNER_HEALTH_URL = "http://127.0.0.1:9100/health"

export const API_ENDPOINTS = {
  health: `${API_BASE_URL}/health`,

  // Auth
  login: `${API_BASE_URL}/api/auth/login`,
  twoFaSetup: `${API_BASE_URL}/api/auth/2fa/setup`,
  twoFaVerify: `${API_BASE_URL}/api/auth/2fa/verify`,
  me: `${API_BASE_URL}/api/auth/me`,

  // Admin - Officers
  officers: `${API_BASE_URL}/api/admin/officers`,
  officer: (userId: string) => `${API_BASE_URL}/api/admin/officers/${userId}`,

  // Persons
  persons: `${API_BASE_URL}/api/persons`,
  personFaceImage: (personId: string) => `${API_BASE_URL}/api/persons/${personId}/face-image`,

  // Enrollment
  enrollFace: `${API_BASE_URL}/api/enroll/face`,
  enrollFingerprint: `${API_BASE_URL}/api/enroll/fingerprint`,

  // Matching
  matchFace: `${API_BASE_URL}/api/match/face`,
  matchFingerprint: `${API_BASE_URL}/api/match/fingerprint`,

  // Combined Verify
  verify: `${API_BASE_URL}/api/verify`,
}

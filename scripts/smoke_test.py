"""Simple smoke tests for the running API.

Usage: python -m scripts.smoke_test
"""
import os
import uuid
import json
import httpx

from app.core.config import ADMIN_EMAIL

BASE = "http://127.0.0.1:8000/api"


def write_test_images():
    b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    os.makedirs("scripts/tmp", exist_ok=True)
    p1 = "scripts/tmp/face.jpg"
    p2 = "scripts/tmp/fingerprint.jpg"
    with open(p1, "wb") as f:
        f.write(__import__("base64").b64decode(b64))
    with open(p2, "wb") as f:
        f.write(__import__("base64").b64decode(b64))
    return p1, p2


def main():
    face_path, fp_path = write_test_images()

    # 1) obtain access token via SKIP_2FA path
    resp = httpx.post(f"{BASE}/auth/2fa/verify", json={"email": ADMIN_EMAIL, "code": "000000"}, timeout=20)
    resp.raise_for_status()
    token = resp.json().get("access_token")
    print("access_token:", token[:32] + "...")

    headers = {"Authorization": f"Bearer {token}"}

    person_id = f"smoke-{uuid.uuid4().hex[:8]}"

    # 2) enroll face
    with open(face_path, "rb") as f:
        files = {"image": ("face.jpg", f, "image/jpeg")}
        data = {"person_id": person_id, "full_name": "Smoke Test"}
        r = httpx.post(f"{BASE}/enroll/face", headers=headers, files=files, data=data, timeout=60)
    print("enroll_face:", r.status_code, r.text)
    r.raise_for_status()

    # 3) match face
    with open(face_path, "rb") as f:
        files = {"image": ("face.jpg", f, "image/jpeg")}
        r = httpx.post(f"{BASE}/match/face", headers=headers, files=files, timeout=60)
    print("match_face:", r.status_code, r.text)
    r.raise_for_status()

    # 4) enroll fingerprint
    with open(fp_path, "rb") as f:
        files = {"image": ("fp.jpg", f, "image/jpeg")}
        data = {"person_id": person_id, "full_name": "Smoke Test", "capture_method": "image_upload"}
        r = httpx.post(f"{BASE}/enroll/fingerprint", headers=headers, files=files, data=data, timeout=60)
    print("enroll_fp:", r.status_code, r.text)
    r.raise_for_status()

    # 5) match fingerprint
    with open(fp_path, "rb") as f:
        files = {"image": ("fp.jpg", f, "image/jpeg")}
        r = httpx.post(f"{BASE}/match/fingerprint", headers=headers, files=files, timeout=60)
    print("match_fp:", r.status_code, r.text)
    r.raise_for_status()

    print("Smoke tests completed successfully.")


if __name__ == "__main__":
    main()

"""Test fingerprint match against API and print raw JSON response.
Usage: python -m scripts.test_fp_match path/to/image.jpg
"""
import sys
import requests

API_URL = "http://localhost:8000/api/match/fingerprint"


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.test_fp_match path/to/image.jpg")
        return
    img_path = sys.argv[1]
    with open(img_path, "rb") as f:
        files = {"image": (img_path, f, "image/jpeg")}
        try:
            resp = requests.post(API_URL, files=files, timeout=30)
            print("Status:", resp.status_code)
            try:
                print(resp.json())
            except Exception:
                print(resp.text)
        except Exception as e:
            print("Request failed:", e)


if __name__ == "__main__":
    main()

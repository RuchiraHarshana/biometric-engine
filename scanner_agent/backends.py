"""
Scanner backend interface and implementations.

Each backend captures a fingerprint image from hardware and returns
raw PNG/grayscale bytes that the ORB engine can process.
"""

import abc
import base64
import io
import os
import platform
from typing import Optional


class ScannerBackend(abc.ABC):
    """Abstract base for all scanner backends."""

    name: str = "base"

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return True if this backend's hardware is detected."""
        ...

    @abc.abstractmethod
    async def capture(self) -> bytes:
        """
        Capture a fingerprint image.
        Returns raw PNG bytes.
        Raises RuntimeError on failure.
        """
        ...


# ─── WBF backend (Windows Biometric Framework) ─────────────────

class WBFBackend(ScannerBackend):
    """
    Uses Windows Biometric Framework via ctypes to capture a raw
    fingerprint sample from the laptop's built-in sensor.

    Requires: Windows 10+ with a WBF-compatible fingerprint reader.
    """

    name = "wbf"

    def is_available(self) -> bool:
        if platform.system() != "Windows":
            return False
        try:
            import ctypes
            winbio = ctypes.windll.LoadLibrary("winbio.dll")
            return winbio is not None
        except (OSError, AttributeError):
            return False

    async def capture(self) -> bytes:
        """
        Capture fingerprint via WBF.
        Uses WinBioCaptureSample to get raw biometric data,
        then converts the sample to a grayscale PNG image.
        """
        import ctypes
        import ctypes.wintypes
        import asyncio
        import struct

        WINBIO_TYPE_FINGERPRINT = 0x00000008
        WINBIO_POOL_SYSTEM = 1
        WINBIO_FLAG_DEFAULT = 0x00000000
        WINBIO_PURPOSE_IDENTIFY = 0x00000010
        WINBIO_DATA_FLAG_RAW = 0x00000001

        winbio = ctypes.windll.LoadLibrary("winbio.dll")

        session_handle = ctypes.c_uint64()
        hr = winbio.WinBioOpenSession(
            WINBIO_TYPE_FINGERPRINT,
            WINBIO_POOL_SYSTEM,
            WINBIO_FLAG_DEFAULT,
            None,  # all units
            0,
            None,  # no database
            ctypes.byref(session_handle),
        )
        if hr != 0:
            raise RuntimeError(f"WinBioOpenSession failed: 0x{hr:08X}")

        try:
            # Run blocking WinBioCaptureSample in a thread
            unit_id = ctypes.c_uint32()
            sample_ptr = ctypes.c_void_p()
            sample_size = ctypes.c_size_t()
            reject_detail = ctypes.c_uint32()

            def _capture_blocking():
                return winbio.WinBioCaptureSample(
                    session_handle,
                    WINBIO_PURPOSE_IDENTIFY,
                    WINBIO_DATA_FLAG_RAW,
                    ctypes.byref(unit_id),
                    ctypes.byref(sample_ptr),
                    ctypes.byref(sample_size),
                    ctypes.byref(reject_detail),
                )

            hr = await asyncio.to_thread(_capture_blocking)
            if hr != 0:
                raise RuntimeError(
                    f"WinBioCaptureSample failed: 0x{hr:08X}, reject=0x{reject_detail.value:08X}"
                )

            # Read raw sample bytes
            raw = (ctypes.c_ubyte * sample_size.value).from_address(sample_ptr.value)
            sample_bytes = bytes(raw)

            # The raw WBF sample includes a WINBIO_BIR header.
            # Skip the header (88 bytes) to get to the raw pixel data.
            # Format: 8-bit grayscale, dimensions from the sensor.
            header_size = 88
            pixel_data = sample_bytes[header_size:]

            # Attempt to infer image dimensions (square assumption as fallback)
            pixel_count = len(pixel_data)
            width = int(pixel_count ** 0.5)
            height = pixel_count // width

            # Convert grayscale pixels → PNG
            return _grayscale_to_png(pixel_data, width, height)

        finally:
            winbio.WinBioCloseSession(session_handle)


# ─── USB scanner backend ───────────────────────────────────────

class USBBackend(ScannerBackend):
    """
    Generic USB fingerprint scanner backend.

    Strategy:
    1. Check for vendor-specific SDK (SecuGen, DigitalPersona, etc.)
    2. Fall back to OpenCV camera capture (some USB scanners present
       as a camera/video device) — captures a frame as the fingerprint.

    For production, replace the camera fallback with your vendor's SDK.
    """

    name = "usb"

    def is_available(self) -> bool:
        # Check if OpenCV can see any video device (scanner may appear as camera)
        try:
            import cv2
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            ok = cap.isOpened()
            cap.release()
            return ok
        except Exception:
            return False

    async def capture(self) -> bytes:
        import cv2
        import asyncio

        def _capture_blocking() -> bytes:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                raise RuntimeError("Cannot open USB scanner / camera device")
            try:
                # Grab a few warm-up frames, then capture
                for _ in range(5):
                    cap.read()
                ret, frame = cap.read()
                if not ret or frame is None:
                    raise RuntimeError("Failed to capture frame from scanner")
                # Convert to grayscale
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                ok, png = cv2.imencode(".png", gray)
                if not ok:
                    raise RuntimeError("Failed to encode scanner image")
                return png.tobytes()
            finally:
                cap.release()

        return await asyncio.to_thread(_capture_blocking)


# ─── Mock backend (for development/testing) ────────────────────

class MockBackend(ScannerBackend):
    """
    Returns a synthetic fingerprint-like image for testing.
    Always available.
    """

    name = "mock"

    def is_available(self) -> bool:
        return True

    async def capture(self) -> bytes:
        import asyncio

        def _generate():
            import numpy as np
            # Generate a synthetic fingerprint-like image (ridges pattern)
            h, w = 300, 300
            img = np.zeros((h, w), dtype=np.uint8)
            for y in range(h):
                for x in range(w):
                    # Simple sine-wave ridge pattern
                    val = int(
                        127 + 127 * np.sin(x * 0.15 + np.sin(y * 0.08) * 3)
                    )
                    img[y, x] = val
            # Add some noise
            noise = np.random.randint(0, 30, (h, w), dtype=np.uint8)
            img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            return img

        img = await asyncio.to_thread(_generate)
        return _grayscale_to_png_numpy(img)


# ─── Helpers ───────────────────────────────────────────────────

def _grayscale_to_png(pixel_data: bytes, width: int, height: int) -> bytes:
    """Convert raw 8-bit grayscale to PNG using minimal zlib (no PIL needed)."""
    import struct
    import zlib

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    # Trim pixel data to width*height
    raw_pixels = pixel_data[: width * height]
    if len(raw_pixels) < width * height:
        raw_pixels += b"\x00" * (width * height - len(raw_pixels))

    # IDAT: each row prefixed with filter byte 0 (None)
    raw_rows = b""
    for y in range(height):
        raw_rows += b"\x00" + raw_pixels[y * width : (y + 1) * width]

    png = b"\x89PNG\r\n\x1a\n"
    # IHDR: width, height, bit_depth=8, color_type=0 (grayscale)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(raw_rows))
    png += _chunk(b"IEND", b"")
    return png


def _grayscale_to_png_numpy(img) -> bytes:
    """Convert a numpy grayscale image to PNG bytes via OpenCV."""
    try:
        import cv2
        ok, buf = cv2.imencode(".png", img)
        if ok:
            return buf.tobytes()
    except ImportError:
        pass
    # Fallback: use raw converter
    h, w = img.shape[:2]
    return _grayscale_to_png(img.tobytes(), w, h)


def get_backend(name: Optional[str] = None) -> ScannerBackend:
    """
    Get a scanner backend by name, or auto-detect the best available one.
    Priority: wbf → usb → mock
    """
    backends = {
        "wbf": WBFBackend,
        "usb": USBBackend,
        "mock": MockBackend,
    }

    if name:
        if name not in backends:
            raise ValueError(f"Unknown backend '{name}'. Choose from: {list(backends.keys())}")
        backend = backends[name]()
        if not backend.is_available():
            raise RuntimeError(f"Scanner backend '{name}' is not available on this system")
        return backend

    # Auto-detect
    for cls in [WBFBackend, USBBackend, MockBackend]:
        b = cls()
        if b.is_available():
            return b

    return MockBackend()  # Absolute fallback

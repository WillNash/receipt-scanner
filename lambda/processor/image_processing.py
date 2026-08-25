import math
import traceback

import cv2
import numpy as np

# --- crop_receipt tuning ---
DETECT_SCALE = 1200
MIN_GAIN = 0.85
PAD_FRAC = 0.025

# --- shared bright/contour region thresholds ---
_BRIGHT_MIN_AREA_FRAC = 0.12
_BRIGHT_MIN_ASPECT = 0.15
_BRIGHT_MAX_ASPECT = 5.0

# --- MSER tuning ---
_MSER_MIN_BBOX = 20
_MSER_MAX_BBOX = 1500
_MSER_MAX_VARIATION = 0.25
_MSER_MIN_FILL = 0.1
_MSER_MAX_FILL = 0.9
_MSER_MIN_ASPECT = 0.15
_MSER_MAX_ASPECT = 6.0
_MSER_BAND_THRESHOLD = 0.60
_MSER_BAND_PAD_FRAC = 0.05


def _to_jpeg(data: bytes) -> bytes:
    """Ensure image bytes are JPEG — converts other formats via cv2."""
    if data[:2] == b"\xff\xd8":
        return data
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Cannot decode image ({len(data)//1024}KB)")
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise ValueError("Failed to encode image as JPEG")
    return buf.tobytes()


def _compute_skew_angle(blocks: list) -> float | None:
    """Compute median skew angle in degrees from Textract LINE polygon top edges.

    Positive means text is tilted counter-clockwise; negative means clockwise.
    Returns None when there are fewer than 3 lines to average over.
    """
    angles = []
    for block in blocks:
        pts = block.get("Geometry", {}).get("Polygon", [])
        if len(pts) < 2:
            continue
        dx = pts[1]["X"] - pts[0]["X"]
        dy = pts[1]["Y"] - pts[0]["Y"]
        if abs(dx) < 1e-6:
            continue
        angles.append(math.degrees(math.atan2(dy, dx)))
    if len(angles) < 3:
        return None
    return float(np.median(angles))


def _deskew_correction(skew: float | None, threshold: float) -> float | None:
    """Return the correction angle to pass to _deskew_image, or None if no correction needed.

    Handles three valid cases:
      • Small skew  (threshold < |skew| ≤ 30°): correct with the exact measured angle.
      • Near ±90°   (|skew| within 10° of 90°): snap to exactly ±90° (portrait/landscape swap).
      • Near ±180°  (|skew| within 10° of 180°): snap to exactly ±180° (upside-down image).

    Angles in the 30–80° and 100–170° bands are ambiguous (likely detection noise) and skipped.
    """
    if skew is None:
        return None
    abs_skew = abs(skew)
    if abs_skew < threshold:
        return None
    if abs_skew <= 30.0:
        return skew
    nearest_90 = round(skew / 90) * 90
    if nearest_90 != 0 and abs(skew - nearest_90) <= 10.0:
        return float(nearest_90)
    return None


def _deskew_image(image_bytes: bytes, angle_deg: float) -> bytes:
    """Rotate image by angle_deg degrees counter-clockwise. Expands canvas to avoid clipping.
    Falls back to original bytes if decoding fails."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return image_bytes
    h, w = img.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    M = cv2.getRotationMatrix2D((cx, cy), angle_deg, 1.0)
    cos_a = abs(M[0, 0])
    sin_a = abs(M[0, 1])
    new_w = int(h * sin_a + w * cos_a)
    new_h = int(h * cos_a + w * sin_a)
    M[0, 2] += (new_w - w) / 2.0
    M[1, 2] += (new_h - h) / 2.0
    rotated = cv2.warpAffine(img, M, (new_w, new_h), borderValue=(255, 255, 255))
    ok, buf = cv2.imencode(".jpg", rotated, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return buf.tobytes() if ok else image_bytes


def crop_receipt(s3, bucket: str, key: str, image_data: bytes | None = None) -> str | None:
    """Crop the receipt from the image using multiple detection methods in priority order."""
    try:
        data = image_data if image_data is not None else s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            print("CROP_SKIPPED: could not decode image")
            return

        h, w = img.shape[:2]
        scale = DETECT_SCALE / max(h, w)
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        small = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)

        result = _find_receipt(small, sw, sh)
        if result is None:
            print("CROP_SKIPPED: no receipt region detected")
            return

        method, sx0, sy0, sx1, sy1 = result

        px, py = int(sw * PAD_FRAC), int(sh * PAD_FRAC)
        left  = max(0, int(max(0, sx0 - px) / scale))
        upper = max(0, int(max(0, sy0 - py) / scale))
        right = min(w,  int(min(sw, sx1 + px) / scale))
        lower = min(h,  int(min(sh, sy1 + py) / scale))

        pixel_ratio = (right - left) * (lower - upper) / (w * h)
        if pixel_ratio >= MIN_GAIN:
            print(f"CROP_SKIPPED ({method}): {pixel_ratio:.0%} — no meaningful gain")
            return None

        cropped = img[upper:lower, left:right]
        ok, buf = cv2.imencode(".jpg", cropped, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not ok:
            print("CROP_SKIPPED: imencode failed")
            return None

        cropped_bytes = buf.tobytes()
        print(
            f"CROP ({method}) {w}x{h} -> {right-left}x{lower-upper} "
            f"{len(data)//1024}KB -> {len(cropped_bytes)//1024}KB ({pixel_ratio:.0%} area)"
        )
        cropped_key = key.replace("uploads/", "cropped/", 1)
        s3.put_object(
            Bucket=bucket,
            Key=cropped_key,
            Body=cropped_bytes,
            ContentType="image/jpeg",
        )
        return cropped_key

    except Exception:
        print(f"CROP_SKIPPED (unexpected):\n{traceback.format_exc()}")
        return None


def _find_receipt(small, sw, sh):
    """Try detection methods in priority order. Returns (method, x0, y0, x1, y1) or None."""
    for method, fn in _CROP_STRATEGIES:
        r = fn(small, sw, sh)
        if r:
            print(f"CROP_METHOD: {method}")
            return (method,) + r
    return None


def _bright_region(small, sw, sh):
    """Find a large bright (white/cream) area — works for receipts on coloured backgrounds."""
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB)
    lightness = lab[:, :, 0]
    k = max(3, sw // 80)
    kernel = np.ones((k, k), np.uint8)
    for thresh in (195, 180, 165):
        _, mask = cv2.threshold(lightness, thresh, 255, cv2.THRESH_BINARY)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel * 4)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        c = max(contours, key=cv2.contourArea)
        if cv2.contourArea(c) < _BRIGHT_MIN_AREA_FRAC * sw * sh:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        if bh > 0 and _BRIGHT_MIN_ASPECT < bw / bh < _BRIGHT_MAX_ASPECT:
            return x, y, x + bw, y + bh
    return None


def _edge_contour(small, sw, sh):
    """Find the largest enclosed region via Canny edge detection."""
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 30, 100)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=3)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(contours, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(c) < _BRIGHT_MIN_AREA_FRAC * sw * sh:
            break
        x, y, bw, bh = cv2.boundingRect(c)
        if bh > 0 and _BRIGHT_MIN_ASPECT < bw / bh < _BRIGHT_MAX_ASPECT:
            return x, y, x + bw, y + bh
    return None


def _dense_band(centres: list, size: int) -> tuple[int, int]:
    hist, edges = np.histogram(centres, bins=40, range=(0, size))
    smoothed = np.convolve(hist, np.ones(5) / 5, mode="same")
    threshold = smoothed.max() * _MSER_BAND_THRESHOLD
    active = [i for i, s in enumerate(smoothed) if s >= threshold]
    if not active:
        return 0, size
    pad = int(size * _MSER_BAND_PAD_FRAC)
    return max(0, int(edges[active[0]]) - pad), min(size, int(edges[active[-1] + 1]) + pad)


def _mser_density(small, sw, sh):
    """Original MSER text-density approach — last-resort fallback."""
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    mser = cv2.MSER_create(5, _MSER_MIN_BBOX, _MSER_MAX_BBOX, _MSER_MAX_VARIATION)
    regions, _ = mser.detectRegions(gray)
    valid_cx, valid_cy = [], []
    for region in regions:
        pts = region.reshape(-1, 1, 2)
        rx, ry, rw, rh = cv2.boundingRect(pts)
        if rw == 0 or rh == 0:
            continue
        bbox_area = rw * rh
        if (_MSER_MIN_ASPECT < rw/rh < _MSER_MAX_ASPECT) and (_MSER_MIN_FILL < len(region)/bbox_area < _MSER_MAX_FILL) and (_MSER_MIN_BBOX < bbox_area < _MSER_MAX_BBOX):
            valid_cx.append(rx + rw / 2)
            valid_cy.append(ry + rh / 2)
    print(f"MSER regions={len(regions)} text-like={len(valid_cx)}")
    if not valid_cx:
        return None
    x0, x1 = _dense_band(valid_cx, sw)
    y0, y1 = _dense_band(valid_cy, sh)
    return x0, y0, x1, y1


_CROP_STRATEGIES = [
    ("bright",   _bright_region),
    ("contour",  _edge_contour),
    ("mser",     _mser_density),
]

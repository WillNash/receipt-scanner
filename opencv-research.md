# OpenCV Receipt Cropping Research

## Problem Context

Receipt (mean brightness 132) lies on a background (mean 122) with only a 10 gray-level global difference. Saturation difference is 5 points. Background is textured fabric so local variance cannot distinguish the two regions. Receipt is a long, narrow strip with dense black text, sometimes rotated 90 degrees.

**Confirmed FAILED approaches:** global brightness threshold, saturation threshold, local variance/edge density, getbbox on bright pixels.

---

## Technique Assessment

### 1. MSER Text Density — HIGH viability

MSER (Maximally Stable Extremal Regions) detects characters, not the receipt boundary. It finds small dark-on-light stable blobs — printed characters. The receipt has hundreds of them; the background fabric has none.

**Strategy:**
1. Detect all MSER regions
2. Filter for character-like geometry (area 30–3000px at working resolution, aspect ratio 0.1–10.0, solidity > 0.3)
3. Compute convex hull of all surviving region points
4. Hull bounds the receipt; its bounding rect is the crop

**Advantage:** Completely bypasses the boundary contrast problem. Handles rotation naturally. Doesn't care what colour the background is.

**Failure modes:** Background with printed patterns or text (newspaper on table) could add false positives. Out-of-focus photos would miss characters.

**Lambda cost:** ~1–3 seconds at 2000px scale.

```python
import cv2
import numpy as np

img = cv2.imread("receipt.jpg")
h, w = img.shape[:2]
scale = 2000 / max(h, w)
small = cv2.resize(img, (int(w * scale), int(h * scale)))
gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

mser = cv2.MSER_create(
    _delta=5,
    _min_area=30,
    _max_area=3000,
    _max_variation=0.25
)
regions, _ = mser.detectRegions(gray)

def is_text_like(region):
    pts = region.reshape(-1, 1, 2)
    x, y, rw, rh = cv2.boundingRect(pts)
    if rw == 0 or rh == 0:
        return False
    aspect = rw / float(rh)
    area = cv2.contourArea(pts)
    bbox_area = rw * rh
    solidity = area / float(bbox_area) if bbox_area > 0 else 0
    return (0.1 < aspect < 10.0) and (solidity > 0.3) and (30 < bbox_area < 5000)

valid = [r for r in regions if is_text_like(r)]

if valid:
    all_pts = np.vstack([r.reshape(-1, 1, 2) for r in valid])
    hull = cv2.convexHull(all_pts)
    hull_full = (hull / scale).astype(np.int32)
    x, y, cw, ch = cv2.boundingRect(hull_full)
    receipt_crop = img[y:y + ch, x:x + cw]
```

---

### 2. Morphological Preprocessing + HoughLinesP — MEDIUM-HIGH viability

Large-kernel morphological dilation/erosion before Canny removes fine texture (fabric weave, receipt text) while preserving long straight lines — the receipt's four edges. HoughLinesP accumulates votes across the full length of those edges, so even a weak 10-gray-level boundary produces enough consistent votes.

Documented in Analytics Vidhya specifically for "ill-lit pictures with noisy boundaries" where contour-finding fails.

**Failure modes:** If Canny produces zero gradient at the receipt boundary even after morphological smoothing.

**Lambda cost:** <0.5 seconds on a 1080px downsampled image.

```python
import cv2
import numpy as np

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(gray, (3, 3), 0)

kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
dilated = cv2.dilate(blurred, kernel, iterations=3)
eroded = cv2.erode(dilated, kernel, iterations=3)

edges = cv2.Canny(eroded, 50, 150)

close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
closed_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, close_kernel)

# Iterative threshold search
threshold = 300
lines = None
while threshold > 50:
    lines = cv2.HoughLines(closed_edges, 1, np.pi / 180, threshold)
    if lines is not None and len(lines) >= 4:
        break
    threshold -= 10
```

---

### 3. GrabCut — MEDIUM viability, best as refinement step

Graph-cut segmentation using Gaussian Mixture Models across all colour channels. LearnOpenCV explicitly states: *"Even images where the background has white and is similar to that of the document, GrabCut allows us to scan them."*

**Critical constraint:** Must downsample to ~800px before GrabCut. At full 4000×3000 it takes 15–30 seconds; at 800px ~1 second with `iterCount=3`.

Best used after MSER or Hough gives a rough bounding box, then GrabCut refines the mask.

```python
import cv2
import numpy as np

img = cv2.imread("receipt.jpg")
target_w, target_h = 800, 600
small = cv2.resize(img, (target_w, target_h))

mask = np.zeros(small.shape[:2], np.uint8)
bgdModel = np.zeros((1, 65), np.float64)
fgdModel = np.zeros((1, 65), np.float64)

border = 20
rect = (border, border, target_w - 2 * border, target_h - 2 * border)
cv2.grabCut(small, mask, rect, bgdModel, fgdModel, 3, cv2.GC_INIT_WITH_RECT)

mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
mask_full = cv2.resize(mask2, (img.shape[1], img.shape[0]),
                       interpolation=cv2.INTER_NEAREST)
result = img * mask_full[:, :, np.newaxis]
```

---

### 4. Bilateral Filter + CLAHE + Canny — MEDIUM viability, fragile

Bilateral filter preserves sharp step-edges while smoothing texture. CLAHE amplifies local contrast. Together they could make the receipt boundary detectable by Canny.

**Critical gotcha:** `sigmaColor` MUST be smaller than the brightness step at the boundary to avoid blurring it away. For a 10 gray-level boundary, use `sigmaColor=5–8`. Typical tutorial values of 75 or 150 will destroy the receipt boundary entirely.

**Lambda cost:** Bilateral with d=5 on 1080px image: ~0.3 seconds.

```python
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
bilateral = cv2.bilateralFilter(gray, d=9, sigmaColor=8, sigmaSpace=8)
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(32, 32))
enhanced = clahe.apply(bilateral)
edges = cv2.Canny(enhanced, 10, 30)
```

---

### 5. Adaptive Thresholding — LOW viability for boundary detection

Designed to find dark pixels (text) within a bright region. NOT designed to find the boundary between two large similar-brightness regions. Useful for binarising receipt text after the receipt has already been cropped, not for detecting the boundary itself.

---

## Lambda Performance Reference

| Operation | Input Size | Approx Time |
|-----------|------------|-------------|
| GrabCut iterCount=5 | 800×600 | ~1 second |
| GrabCut iterCount=3 | 800×600 | ~0.6 seconds |
| GrabCut iterCount=5 | 4000×3000 full res | ~15–30 seconds — too slow |
| Bilateral filter d=9 | 4000×3000 | ~2–5 seconds |
| Bilateral filter d=5 | 1080px scaled | ~0.3 seconds |
| MSER detection | 2000px scaled | ~1–3 seconds |
| Canny + HoughLines | 1080px scaled | <0.5 seconds |
| Morphological ops | any | <0.1 seconds |
| CLAHE | 4000×3000 | <0.3 seconds |

---

## Package Size for Lambda

**opencv-python-headless** v5.x (July 2026):
- Installed size: ~60–90 MB
- Fits within Lambda layer limit (250 MB unzipped)
- No pre-built Python 3.12 layers exist — must build your own

**scikit-image** is NOT a meaningful alternative: it requires scipy (~86 MB) and lacks MSER, GrabCut, bilateral filter, and HoughLines.

### Building an OpenCV Lambda layer (Python 3.12)

```bash
mkdir -p python/lib/python3.12/site-packages
pip install \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --target python/lib/python3.12/site-packages/ \
  opencv-python-headless numpy
zip -r opencv-layer.zip python/
aws lambda publish-layer-version \
  --layer-name opencv-python312-headless \
  --compatible-runtimes python3.12 \
  --zip-file fileb://opencv-layer.zip
```

---

## Key Gotchas

- **Canny apertureSize**: use 5 or 7 (larger Sobel kernel) to detect larger-scale edges and reduce sensitivity to fine texture
- **CLAHE tileGridSize**: for a 4000×3000 image with a ~400px-wide receipt, use `(32, 32)` so the boundary falls between tiles
- **MSER `_max_area`**: must be scaled with working resolution — re-tune after downsampling
- **GrabCut**: NOT suitable at full 4000×3000 resolution in Lambda
- **`approxPolyDP` epsilon**: standard `0.02 * perimeter` may over-simplify a long narrow receipt; try `0.01` or `0.015`
- **Morphological pre-Canny kernel**: keep under 9×9 and fewer than 5 iterations or it will also suppress the receipt edge

---

## Recommended Approach

**Try MSER first.** It is the only technique that does not rely on detecting the receipt boundary — it detects receipt content (characters) instead. If the background contains printed material or high-contrast texture, combine MSER with GrabCut as a refinement step.

Sources: PyImageSearch (auto-Canny, GrabCut), LearnOpenCV (document scanner, GrabCut), Analytics Vidhya (HoughLines document scanner), Scanbot SDK (document edge detection), OpenCV docs (MSER, morphology, bilateral), PyPI (opencv-python-headless).

#!/usr/bin/env python3
"""
Overlay word bounding boxes and per-row curl baselines on a receipt image.

  Green rectangles  — one per Textract WORD, from the debug JSON
  Blue parabolas    — per-row de-curl baseline:
                      y_observed(x) = y_flat_row + curl_a·x² + curl_b·x

Usage:
    python3 scripts/visualize_words.py IMAGE DEBUG_JSON [OUTPUT]

IMAGE       Any image file (JPEG, PNG, …)
DEBUG_JSON  The _textract.json debug file — needs a top-level "words" list
            with fields: top, left, width, height (0-1 fractions), row (int)
OUTPUT      Optional output path (default: <IMAGE_STEM>_annotated.png)

Dependencies:
    pip install matplotlib pillow numpy
"""

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


# ── Curl estimation ───────────────────────────────────────────────────────────
# Mirrors Phase 1 + Phase 2 of line_grouping.group_blocks exactly.

def estimate_curl(words: list) -> tuple[float, float]:
    """Return (curl_a, curl_b) from word positions."""
    if len(words) < 3:
        return 0.0, 0.0

    def top(w):  return w["top"]
    def left(w): return w["left"]

    by_y = sorted(words, key=top)
    gaps = [top(by_y[i + 1]) - top(by_y[i]) for i in range(len(by_y) - 1)]
    large_gaps = sorted(g for g in gaps if g >= 0.005)
    line_height = large_gaps[len(large_gaps) // 2] if large_gaps else 0.012

    cand = []
    for A in words:
        for B in words:
            if A is B:
                continue
            dx = left(B) - left(A)
            if dx < 0.15:
                continue
            dy = top(B) - top(A)
            if abs(dy) > 1.5 * line_height:
                continue
            cand.append((left(A) + left(B), dy / dx))

    if len(cand) < 3:
        return 0.0, 0.0

    raw_slopes = sorted(s for _, s in cand)
    n = len(raw_slopes)
    k = max(3, (n + 1) // 2)
    best_range, best_i = float("inf"), 0
    for i in range(n - k + 1):
        r = raw_slopes[i + k - 1] - raw_slopes[i]
        if r < best_range:
            best_range, best_i = r, i
    s_lo, s_hi = raw_slopes[best_i], raw_slopes[best_i + k - 1]
    dense = [(sx, s) for sx, s in cand if s_lo <= s <= s_hi]

    ts_a_vals = []
    for i in range(len(dense)):
        for j in range(i + 1, len(dense)):
            d_sx = dense[j][0] - dense[i][0]
            if abs(d_sx) < 0.15:
                continue
            ts_a_vals.append((dense[j][1] - dense[i][1]) / d_sx)
    curl_a = sorted(ts_a_vals)[len(ts_a_vals) // 2] if ts_a_vals else 0.0

    residuals = sorted(s - curl_a * sx for sx, s in dense)
    curl_b = residuals[len(residuals) // 2]
    return curl_a, curl_b


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    img_path  = Path(sys.argv[1])
    json_path = Path(sys.argv[2])
    out_path  = (Path(sys.argv[3]) if len(sys.argv) > 3
                 else img_path.with_name(img_path.stem + "_annotated.png"))

    img = plt.imread(str(img_path))
    if img.dtype != np.uint8:
        img = (img * 255).astype(np.uint8)
    H, W = img.shape[:2]

    with open(json_path) as f:
        data = json.load(f)
    words = data.get("words", [])
    if not words:
        sys.exit("No 'words' key in JSON — is this a _textract.json debug file?")

    curl_a, curl_b = estimate_curl(words)
    print(f"curl_a={curl_a:.6f}  curl_b={curl_b:.6f}")

    def y_flat(w: dict) -> float:
        x = w["left"]
        return w["top"] - curl_a * x * x - curl_b * x

    # Group words by row
    row_words: dict[int, list] = {}
    for w in words:
        row_words.setdefault(w.get("row", -1), []).append(w)

    # Figure sized to the image at 100 dpi
    fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
    ax.imshow(img, origin="upper")
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")

    x_frac = np.linspace(0.0, 1.0, 400)

    for row_idx, rwords in sorted(row_words.items()):
        # Green bounding box for every word in this row
        for w in rwords:
            rx = w["left"]   * W
            ry = w["top"]    * H
            rw = w["width"]  * W
            rh = w["height"] * H
            ax.add_patch(mpatches.Rectangle(
                (rx, ry), rw, rh,
                linewidth=1.5, edgecolor="lime", facecolor="none",
            ))

        if row_idx < 0:
            continue

        # Blue parabola at this row's mean y_flat
        y_flat_row = sum(y_flat(w) for w in rwords) / len(rwords)
        y_px = (y_flat_row + curl_a * x_frac ** 2 + curl_b * x_frac) * H
        ax.plot(x_frac * W, y_px, color="dodgerblue", linewidth=1.2, alpha=0.75)

    fig.tight_layout(pad=0)
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {out_path}  ({len(words)} words, {len(row_words)} rows)")


if __name__ == "__main__":
    main()

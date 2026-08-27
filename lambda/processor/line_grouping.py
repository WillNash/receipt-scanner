import re

_QTY_RE = re.compile(r'^\d+\s*@')


def group_blocks(blocks: list) -> tuple[list[list], float, float]:
    """Group Textract LINE blocks into receipt rows using parabolic de-curl and chaining.

    Phase 1 — Calibrate: derive line height from the median of Y-gaps between
    consecutive blocks, ignoring sub-0.5% gaps (intra-word noise).

    Phase 2 — Estimate curl: model the receipt deformation as
    Y_observed = Y_true + a*X^2 + b*X.  For any same-row pair (A, B):
      (Y_B - Y_A) / (X_B - X_A) = a*(X_A + X_B) + b
    Collect candidate same-row pairs (B to the right of A by ≥ 15%, Y-gap ≤
    1.5 × line_height).  Apply LMS (minimum-range half-sample) to find the
    tightest slope cluster, then fit slope = a*sum_X + b via Theil-Sen on pairs
    with |Δsum_X| > 0.15.  The de-curled coordinate y_flat(b) = Y(b) -
    a*X(b)^2 - b*X(b) is used for all subsequent Y comparisons.  For a flat
    receipt (a=b=0) y_flat degrades to the raw Y.

    Phase 3 — Mark multi-buy anchors: scan for quantity-indicator blocks
    (text like "2@", "4 @") and mark the description row immediately above each
    one as a no-price anchor.

    Phase 4 — Chain: pop the leftmost unassigned block, then walk right picking
    the horizontally nearest block within step_tol of the current tail's y_flat.
    The tolerance resets to each newly added block's y_flat so it follows
    residual row curvature.  No-price anchors skip right-edge blocks (left > 65%).

    Phase 5 — Absorb price orphans: single-block rows whose block sits in the
    right-hand price column (X > 65%) are merged into the nearest other row
    within 2 × step_tol in y_flat space.  No-price anchor rows are excluded.

    Returns (rows, line_height, step_tol) where rows is a list of block lists
    in top-to-bottom reading order.
    """
    if not blocks:
        return [], 0.0, 0.0

    def _top(b):  return b["Geometry"]["BoundingBox"]["Top"]
    def _left(b): return b["Geometry"]["BoundingBox"]["Left"]

    # Phase 1 — calibrate line height for this specific receipt
    by_y = sorted(blocks, key=_top)
    gaps = [_top(by_y[i + 1]) - _top(by_y[i]) for i in range(len(by_y) - 1)]
    large_gaps = sorted(g for g in gaps if g >= 0.005)
    line_height = large_gaps[len(large_gaps) // 2] if large_gaps else 0.012
    step_tol = line_height * 0.4

    # Phase 2 — estimate parabolic curl deformation
    # For a same-row pair (A, B) with X_B > X_A:
    #   slope_AB = (Y_B - Y_A) / (X_B - X_A) = a*(X_A + X_B) + b
    # Collect candidate same-row pairs and fit slope = a*sum_X + b via Theil-Sen.
    cand = []
    for A in blocks:
        for B in blocks:
            if A is B:
                continue
            dx = _left(B) - _left(A)
            if dx < 0.15:
                continue
            dy = _top(B) - _top(A)
            if abs(dy) > 1.5 * line_height:
                continue
            cand.append((_left(A) + _left(B), dy / dx))

    curl_a, curl_b = 0.0, 0.0
    if len(cand) >= 3:
        raw_slopes = sorted(s for _, s in cand)
        n = len(raw_slopes)
        k = max(3, (n + 1) // 2)
        # LMS: minimum-range half-sample isolates the tightest slope cluster.
        best_range, best_i = float("inf"), 0
        for i in range(n - k + 1):
            r = raw_slopes[i + k - 1] - raw_slopes[i]
            if r < best_range:
                best_range, best_i = r, i
        s_lo, s_hi = raw_slopes[best_i], raw_slopes[best_i + k - 1]
        dense = [(sx, s) for sx, s in cand if s_lo <= s <= s_hi]
        # Theil-Sen on the dense cluster for the parabolic coefficient.
        # Require |Δsum_X| > 0.15 so only pairs at meaningfully different X
        # positions contribute; otherwise curl_a stays 0 (linear model).
        ts_a_vals = []
        for i in range(len(dense)):
            for j in range(i + 1, len(dense)):
                d_sx = dense[j][0] - dense[i][0]
                if abs(d_sx) < 0.15:
                    continue
                ts_a_vals.append((dense[j][1] - dense[i][1]) / d_sx)
        if ts_a_vals:
            curl_a = sorted(ts_a_vals)[len(ts_a_vals) // 2]
        residuals = sorted(s - curl_a * sx for sx, s in dense)
        curl_b = residuals[len(residuals) // 2]

    def _flat(b):
        x = _left(b)
        return _top(b) - curl_a * x * x - curl_b * x

    # Phase 3 — mark multi-buy anchor rows (uses y_flat for Y comparisons)
    qty_indicators = [
        b for b in blocks
        if _QTY_RE.match(b.get("Text", "")) and 0.20 <= _left(b) <= 0.55
    ]
    no_price_ids: set[int] = set()
    for qb in qty_indicators:
        qy = _flat(qb)
        best_b, best_gap = None, float("inf")
        for b in blocks:
            if b is qb or _left(b) > 0.30:
                continue
            gap = qy - _flat(b)
            if 0 < gap < line_height * 3 and gap < best_gap:
                best_gap, best_b = gap, b
        if best_b is not None:
            no_price_ids.add(id(best_b))

    # Phase 4 — chain leftmost-first in de-curled Y space
    unassigned = sorted(blocks, key=lambda b: (_left(b), _flat(b)))
    rows: list[list] = []

    while unassigned:
        chain = [unassigned.pop(0)]
        anchor_no_price = id(chain[0]) in no_price_ids
        while True:
            cur_x = _left(chain[-1])
            cur_y = _flat(chain[-1])
            best: dict | None = None
            best_dx = float("inf")
            for b in unassigned:
                bx = _left(b)
                if bx <= cur_x:
                    continue
                if anchor_no_price and bx > 0.65:
                    continue
                if abs(_flat(b) - cur_y) <= step_tol:
                    dx = bx - cur_x
                    if dx < best_dx:
                        best_dx = dx
                        best = b
            if best is None:
                break
            chain.append(best)
            unassigned.remove(best)
        rows.append(chain)

    # Phase 5 — absorb isolated right-edge price blocks
    i = 0
    while i < len(rows):
        if len(rows[i]) != 1 or _left(rows[i][0]) <= 0.65:
            i += 1
            continue
        orphan_y = _flat(rows[i][0])
        best_j, best_gap = None, float("inf")
        for j, other in enumerate(rows):
            if j == i or id(other[0]) in no_price_ids:
                continue
            gap = min(abs(_flat(b) - orphan_y) for b in other)
            if gap <= step_tol * 2 and gap < best_gap:
                best_gap, best_j = gap, j
        if best_j is None:
            i += 1
            continue
        rows[best_j] = sorted(rows[best_j] + rows[i], key=_left)
        rows.pop(i)

    rows.sort(key=lambda row: min(_flat(b) for b in row))
    return rows, line_height, step_tol

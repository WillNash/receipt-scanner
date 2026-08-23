def group_blocks(blocks: list) -> tuple[list[list], float, float]:
    """Group Textract LINE blocks into receipt rows using two-phase chaining.

    Phase 1 — Calibrate: derive line height from the median of Y-gaps between
    consecutive blocks, ignoring sub-0.5% gaps (intra-word noise).

    Phase 2 — Chain: pop the leftmost unassigned block (descriptions always
    anchor the left edge), then walk right picking the horizontally nearest
    block within a rolling Y-tolerance derived from the calibrated line height.
    The tolerance resets to each newly added block's Y so it follows any
    curvature without drifting from the row origin.

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

    # Phase 2 — chain leftmost-first so descriptions always start chains
    unassigned = sorted(blocks, key=lambda b: (_left(b), _top(b)))
    rows: list[list] = []

    while unassigned:
        chain = [unassigned.pop(0)]
        while True:
            cur_x = _left(chain[-1])
            cur_y = _top(chain[-1])
            best: dict | None = None
            best_dx = float("inf")
            for b in unassigned:
                bx = _left(b)
                if bx <= cur_x:
                    continue
                if abs(_top(b) - cur_y) <= step_tol:
                    dx = bx - cur_x
                    if dx < best_dx:
                        best_dx = dx
                        best = b
            if best is None:
                break
            chain.append(best)
            unassigned.remove(best)
        rows.append(chain)

    rows.sort(key=lambda row: min(_top(b) for b in row))
    return rows, line_height, step_tol

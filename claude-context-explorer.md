# Image Processing Pipeline — /workspace/active_repo/lambda/processor/

## File Inventory

Two handler generations exist:

- `/workspace/active_repo/lambda/processor/handler.py` — ACTIVE handler (modular, uses Bedrock + Textract `detect_document_text` via `Bytes`)
- `/workspace/active_repo/lambda/processor/package/handler.py` — ARCHIVED older handler (monolithic, uses Textract `analyze_document` with FORMS via S3Object, regex parser, no Bedrock). Not imported by the active handler.
- `/workspace/active_repo/lambda/processor/image_processing.py` — cropping, JPEG conversion, deskew
- `/workspace/active_repo/lambda/processor/textract_pipeline.py` — Textract call + block grouping dispatch
- `/workspace/active_repo/lambda/processor/line_grouping.py` — parabolic de-curl row grouping algorithm
- `/workspace/active_repo/lambda/processor/bedrock_extraction.py` — Bedrock Claude call + post-processing

---

## Full Call Chain (Active Handler)

### 1. Entry — handler.py:69 lambda_handler(event, context)
Iterates SQS records, calls process_record(record) for each.
process_record (handler.py:80) parses the S3 event and calls _process_s3_record(bucket, key, job_id).

### 2. S3 Download — handler.py:133
```python
image_data = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
```
Type: bytes. No size check. Raw original upload (any format; up to 20 MB upload limit enforced by frontend/API).
SHA-256 hash computed from these raw bytes for dedup.

### 3. analyze_receipt(bucket, key, job_id, user_id, image_data=image_data) — handler.py:241
Main orchestration function.

---

### 4. Cropping — image_processing.crop_receipt(s3, bucket, key, image_data=image_data) — image_processing.py:108

Data flow inside crop_receipt:

a. Uses the image_data: bytes already in memory (avoids a second S3 fetch).

b. np.frombuffer(data, dtype=np.uint8) -> 1-D uint8 numpy array. Then cv2.imdecode(arr, cv2.IMREAD_COLOR) -> numpy ndarray (H, W, 3) uint8 BGR. OpenCV handles JPEG/PNG/HEIC/etc.

c. Detection thumbnail (image_processing.py:119-121): Image downscaled for detection only.
   - DETECT_SCALE = 1200 (longest side of thumbnail)
   - scale = 1200 / max(h, w)
   - small = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA) -> numpy (sh, sw, 3) uint8
   - Thumbnail is used ONLY for detection; actual crop is applied to full-resolution img.

d. Three detection strategies tried in order (_CROP_STRATEGIES at image_processing.py:248):

   - _bright_region(small, sw, sh) (image_processing.py:176): LAB lightness thresholding (195->180->165), morphological close/open, largest contour bounding rect. Requires area >= 12% of thumbnail and aspect ratio 0.15-5.0.

   - _edge_contour(small, sw, sh) (image_processing.py:198): Canny edges (30/100) on grayscale, 3-iter dilate, largest valid contour. Same area/aspect gate.

   - _mser_density(small, sw, sh) (image_processing.py:225): MSER on grayscale thumbnail (delta=5, min_area=20, max_area=1500, max_variation=0.25). Filters character-like blobs (aspect 0.15-6.0, fill 0.1-0.9, area 20-1500 px^2). Projects blob centres onto X/Y axes, smoothed density histogram (40 bins, window-5), finds high-density band (>=60% of peak), pads by 5% of axis length.

e. Skip condition (image_processing.py:137): If crop bounding box covers >= 85% (MIN_GAIN = 0.85) of original pixel area, cropping is skipped. Returns None.

f. Crop and encode (image_processing.py:141-158): Crop applied to full-resolution img (numpy slice). Encoded to JPEG at quality 92 (cv2.IMWRITE_JPEG_QUALITY, 92) regardless of input format. Result: bytes. Saved to S3 under cropped/<user_id>/<job_id>.ext (key formed by replacing "uploads/" with "cropped/"). Returns new S3 key.

---

### 5. Post-crop image selection — handler.py:246-250

If cropping succeeded: fetch the saved cropped JPEG from S3 -> data: bytes (already JPEG).

If cropping was skipped: use original image_data: bytes and call _to_jpeg(raw) (image_processing.py:29):
- If bytes start with \xff\xd8 (JPEG magic): returned unchanged.
- Otherwise: cv2.imdecode -> numpy array -> cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92]) -> bytes.

At this point data is always a JPEG bytes object. No resizing is done to the image going into Textract — it is full resolution (or full crop resolution).

---

### 6. Deskew pipeline — handler.py:184 _run_deskew_pipeline(data, skew_threshold=1.0)

a. First Textract call with current data: bytes (full-res JPEG). See step 7.

b. _compute_skew_angle(tr.blocks) (image_processing.py:43): Median angle in degrees from LINE block polygon top-edge vectors. Returns None if fewer than 3 lines.

c. _deskew_correction(skew, threshold=1.0) (image_processing.py:64): Returns None if |skew| < 1.0 deg. Corrects small skew (1-30 deg), snaps near +-90 or +-180 to cardinal angles. Ignores 30-80 and 100-170 degree bands (ambiguous/noise).

d. If correction needed: _deskew_image(data: bytes, angle_deg: float) (image_processing.py:87):
   - cv2.imdecode -> numpy (H, W, 3)
   - Rotation matrix via cv2.getRotationMatrix2D; canvas EXPANDED to avoid clipping
   - cv2.warpAffine with white fill (255,255,255) -> numpy array
   - cv2.imencode(".jpg", rotated, [cv2.IMWRITE_JPEG_QUALITY, 92]) -> bytes
   - Falls back to original bytes if decode fails

e. Second Textract call (only if deskew applied) with the rotated JPEG bytes.

f. If deskew was applied AND a cropped key exists, deskewed image overwrites the S3 cropped object (handler.py:255).

Returns (final_data: bytes, tr: TextractResult, skew, correction, deskew_applied).

---

### 7. Textract call — textract_pipeline.py:25 _textract_lines(image_bytes: bytes)

```python
resp = textract.detect_document_text(Document={"Bytes": image_bytes})
```

- API: detect_document_text (NOT analyze_document). No FeatureTypes — raw text detection only.
- Image passed as raw bytes in request body ("Bytes" key), NOT via S3 reference.
- AWS hard limit for Bytes mode: 10 MB. No size guard is implemented before this call.
- Returns all Blocks. Filters into LINE blocks (for skew + grouping) and WORD blocks (for group_blocks).
- Calls group_blocks(words) from line_grouping.py (see step 8).
- Returns TextractResult dataclass: .text (newline-joined lines), .lines, .blocks, .words, .rows, .line_height, .step_tol.

---

### 8. Line grouping — line_grouping.py:6 group_blocks(blocks: list)

Input: list of Textract WORD block dicts (normalised 0-1 coordinate geometry).

Five-phase algorithm (all coordinates normalised 0-1, no pixel manipulation):
1. Calibrate line height from Y-gap median.
2. Estimate parabolic de-curl coefficients (Theil-Sen on same-row candidate pairs).
3. Mark multi-buy anchor rows ("N @" patterns).
4. Chain blocks left-to-right in de-curled Y space.
5. Absorb isolated right-edge price orphan blocks.

Returns (rows: list[list[dict]], line_height: float, step_tol: float). No image data involved.

---

### 9. Bedrock call — bedrock_extraction.py:153 _run_bedrock(receipt_text: str)

Input: tr.text — plain str (newline-separated lines, same-row items separated by spaces).
Calls bedrock.converse with structured tool use (extract_receipt tool).
Default model: anthropic.claude-3-5-haiku-20241022-v1:0 (BEDROCK_MODEL_ID env var).
Returns (extracted: dict, usage: dict).

---

### 10. Post-processing — handler.py:258-264, bedrock_extraction.py

- _validate_classification(extracted): Clamps out-of-vocab store_category/item_category/nova_group.
- _fix_weighted_item_prices(items): For fractional-quantity items, recomputes unit_price = line_total / quantity if they disagree by >= $0.01.
- _compute_net_prices(items): Sets price = line_total + discount for each item.

---

## Data Types at Each Stage

| Stage | Variable | Type |
|---|---|---|
| S3 download | image_data | bytes (raw upload, any format) |
| After hash | image_data | bytes (same) |
| crop_receipt internal decode | img | numpy ndarray (H, W, 3) uint8 BGR |
| Detection thumbnail | small | numpy ndarray (sh, sw, 3) uint8 BGR |
| Crop region back-projected | cropped | numpy ndarray slice (H', W', 3) uint8 BGR |
| After crop encode | cropped_bytes | bytes JPEG quality-92 |
| data entering deskew | data | bytes JPEG (from S3 cropped or _to_jpeg) |
| _deskew_image internal | img/rotated | numpy ndarray uint8 BGR |
| After deskew encode | (return) | bytes JPEG quality-92 |
| Textract Bytes payload | image_bytes | bytes JPEG |
| Textract response | tr | TextractResult dataclass |
| Bedrock input | receipt_text | str |

---

## Size-Related Logic — Complete Inventory

1. DETECT_SCALE = 1200 (image_processing.py:8): Thumbnail longest-side for all three crop detection methods. Detection only — no effect on what goes to Textract.

2. MIN_GAIN = 0.85 (image_processing.py:9): Crop suppressed if bounding box covers >= 85% of original pixel count.

3. MSER blob filters (image_processing.py:17-19): _MSER_MIN_BBOX = 20, _MSER_MAX_BBOX = 1500 (pixel area in thumbnail-space), _MSER_MAX_VARIATION = 0.25. Applied at the 1200-px scale.

4. JPEG quality 92 used consistently: _to_jpeg (line 37), _deskew_image (line 104), crop_receipt crop encode (line 142).

5. NO explicit byte-size check before the Textract Bytes call. AWS detect_document_text with Bytes has a hard 10 MB limit. A large full-resolution crop from a 20 MB upload could exceed this. The code does not check or compress-to-fit before sending.

6. NO resizing to a fixed resolution anywhere in the pipeline going into Textract. Full-resolution crop (or full-resolution JPEG-converted original) is sent.

7. Frontend upload limit: 20 MB enforced by API/frontend. Processor has no corresponding guard.

---

## Legacy Handler Differences (package/handler.py)

- Uses textract.analyze_document(..., FeatureTypes=["FORMS"]) passing S3Object reference (not Bytes), so the 10 MB Bytes limit does NOT apply there.
- crop_receipt overwrites the ORIGINAL S3 key in-place (not a separate cropped/ prefix).
- Detection scale MSER_SCALE = 2000 (not 1200).
- JPEG quality 95 for JPEG inputs; PNG (lossless) for non-JPEG inputs.
- No deskew logic.
- No Bedrock; uses regex state-machine parser (extract_line_items, reconcile_line_items) instead.
- No image_hashes dedup table integration.

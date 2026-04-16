"""
SnapMbed — Scanner
Walks a folder, finds all media files and their JSON sidecars.
Returns a 5-tuple: (all_files, json_map, media_files, raw_files, stats)
"""

import os
import re

JPEG_EXTS  = {".jpg", ".jpeg", ".jfif", ".jpe"}
IMAGE_EXTS = JPEG_EXTS | {".png", ".webp", ".tiff", ".tif", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v"}
RAW_EXTS   = {".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".raf", ".pef", ".srw"}
SKIP_EXTS  = {".gif", ".bmp", ".avi", ".mkv", ".wmv", ".svg", ".pdf", ".psd"}
ALL_MEDIA  = IMAGE_EXTS | VIDEO_EXTS | RAW_EXTS


def scan_folder(folder_path):
    """
    Walk folder_path recursively.
    Returns:
        all_files   dict  rel_path (lower, forward-slash) -> rel_path (original case)
        json_map    dict  media_rel -> json_rel  (both original-case)
        media_files list  of rel paths for processable media (IMAGE_EXTS + VIDEO_EXTS)
        raw_files   list  of rel paths for RAW files (skipped safely)
        stats       dict  summary counts
    """
    all_files_lower = {}   # lower/normalised rel -> original-case rel
    all_files       = {}   # original-case rel -> abs path
    json_map        = {}   # media_rel -> json_rel
    media_files     = []
    raw_files       = []
    skipped         = {}

    # ── Pass 1: index every file ──────────────────────────────
    for root, dirs, files in os.walk(folder_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            abs_path = os.path.join(root, fname)
            rel_orig = os.path.relpath(abs_path, folder_path).replace("\\", "/")
            rel_low  = rel_orig.lower()
            all_files_lower[rel_low] = rel_orig
            all_files[rel_orig]      = abs_path

    # ── Pass 2: match JSON sidecars to media ─────────────────
    for rel_low, rel_orig in all_files_lower.items():
        if not rel_low.endswith(".json"):
            continue
        media_rel = _find_media_for_json(rel_low, rel_orig, all_files_lower)
        if media_rel and media_rel not in json_map:
            json_map[media_rel] = all_files_lower[rel_low]  # original-case json rel

    # ── Pass 3: classify media ────────────────────────────────
    for rel_orig in all_files:
        ext = os.path.splitext(rel_orig.lower())[1]
        if ext in SKIP_EXTS:
            skipped[ext] = skipped.get(ext, 0) + 1
        elif ext in RAW_EXTS:
            raw_files.append(rel_orig)
        elif ext in IMAGE_EXTS or ext in VIDEO_EXTS:
            media_files.append(rel_orig)

    media_files.sort()
    raw_files.sort()

    # Count formats
    fmt_counts = {}
    for p in media_files:
        ext = os.path.splitext(p.lower())[1]
        fmt_counts[ext] = fmt_counts.get(ext, 0) + 1

    # Non-processable files that DO have a JSON (informational warning)
    warned = {}
    for med_rel in list(json_map.keys()):
        ext = os.path.splitext(med_rel.lower())[1]
        if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
            warned[ext] = warned.get(ext, 0) + 1

    jpeg_matched = sum(
        1 for p in media_files if p in json_map
    )

    stats = {
        "total_media":  len(media_files),
        "matched_json": jpeg_matched,
        "no_json":      len(media_files) - jpeg_matched,
        "raw_count":    len(raw_files),
        "skipped":      skipped,
        "fmt_counts":   fmt_counts,
        "warned":       warned,
    }

    return all_files, json_map, media_files, raw_files, stats


def _find_media_for_json(json_low, json_orig, all_files_lower):
    """
    Try all known Google Takeout JSON naming patterns.
    Returns the lower-normalised rel path of the matching media file, or None.
    """
    MEDIA_EXT_PAT = (
        r"(jpg|jpeg|jfif|jpe|png|webp|tiff?|heic|heif"
        r"|mp4|mov|m4v|cr2|cr3|nef|arw|dng|orf|rw2|raf|pef|srw)"
    )

    # Pattern 1: strip .json directly  →  photo.jpg
    stripped = json_low[:-5]
    if stripped in all_files_lower:
        return stripped

    base = json_low[:-5]  # everything before .json

    # Pattern 2: .supplemental-metadata.json
    m = re.match(
        rf'^(.+\.{MEDIA_EXT_PAT})\.supplemental-metadata$',
        base, re.IGNORECASE)
    if m and m.group(1) in all_files_lower:
        return m.group(1)

    # Pattern 3: truncated supplemental  (.supp, .supplem, etc.)
    m = re.match(
        rf'^(.+\.{MEDIA_EXT_PAT})\.supp(?:l(?:e(?:m(?:e(?:n(?:t(?:a(?:l(?:-metadata)?)?)?)?)?)?)?)?)?$',
        base, re.IGNORECASE)
    if m and m.group(1) in all_files_lower:
        return m.group(1)

    # Pattern 4: any suffix after known image ext (Google truncation)
    m = re.match(
        rf'^(.+\.{MEDIA_EXT_PAT})[^/\\]*$',
        base, re.IGNORECASE)
    if m and m.group(1) in all_files_lower:
        return m.group(1)

    # Pattern 5: base name only  photo.json → photo.jpg
    name_no_ext = os.path.splitext(json_low)[0]
    for ext in (".jpg", ".jpeg", ".jfif", ".jpe", ".png", ".webp",
                ".tiff", ".tif", ".heic", ".heif", ".mp4", ".mov", ".m4v"):
        c = name_no_ext + ext
        if c in all_files_lower:
            return c

    return None

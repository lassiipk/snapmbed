"""
core/scanner.py — finds all image files and their JSON sidecars.
"""
import os
from pathlib import Path

JPEG_EXTS   = {".jpg", ".jpeg", ".jpe", ".jfif"}
IMAGE_EXTS  = JPEG_EXTS | {".png", ".webp", ".heic", ".heif", ".tiff", ".tif", ".bmp"}
VIDEO_EXTS  = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}
ALL_MEDIA   = IMAGE_EXTS | VIDEO_EXTS
WRITABLE_EXTS = JPEG_EXTS | {".png", ".webp", ".heic", ".heif", ".tiff", ".tif", ".mp4", ".mov", ".m4v"}
SKIP_EXTS   = {".bmp", ".gif", ".avi", ".mkv", ".svg", ".pdf", ".psd"}


class ScanResult:
    def __init__(self):
        self.media_files: list = []
        self.json_map: dict = {}
        self.skipped_formats: dict = {}
        self.no_json: list = []
        self.total_json: int = 0
        self.folder: str = ""

    @property
    def writable(self):
        return [p for p in self.media_files
                if p in self.json_map and Path(p).suffix.lower() in WRITABLE_EXTS]

    @property
    def matched(self):
        return len(self.json_map)

    @property
    def total(self):
        return len(self.media_files)


def _find_json_for(media_rel: str, all_files: dict):
    lower = media_rel.lower()
    base_no_ext = os.path.splitext(lower)[0]
    ext = os.path.splitext(lower)[1]
    parent_lower = os.path.dirname(lower)
    stem = os.path.basename(base_no_ext)

    # Try explicit patterns
    candidates = [
        lower + ".json",
        lower + ".supplemental-metadata.json",
        lower + ".supp.json",
        base_no_ext + ".json",
    ]
    for c in candidates:
        if c in all_files:
            return all_files[c]

    # Fuzzy: any .json in same dir starting with image basename
    for lp, orig in all_files.items():
        if not lp.endswith(".json"):
            continue
        if os.path.dirname(lp) != parent_lower:
            continue
        bn = os.path.basename(lp)
        if bn.startswith(os.path.basename(lower)) or bn.startswith(stem):
            return orig

    return None


def scan_folder(folder: str, progress_cb=None):
    result = ScanResult()
    result.folder = folder
    all_files: dict = {}
    media_found: list = []

    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, folder)
            all_files[rel.lower().replace("\\", "/")] = rel.replace("\\", "/")
            ext = os.path.splitext(fname)[1].lower()
            if ext in ALL_MEDIA:
                media_found.append(rel.replace("\\", "/"))

    result.total_json = sum(1 for p in all_files if p.endswith(".json"))
    total = len(media_found)

    for i, rel in enumerate(media_found):
        if progress_cb and i % 50 == 0:
            progress_cb(i, total, os.path.basename(rel))
        ext = os.path.splitext(rel)[1].lower()
        result.media_files.append(rel)
        if ext in SKIP_EXTS:
            result.skipped_formats[ext] = result.skipped_formats.get(ext, 0) + 1
            continue
        json_rel = _find_json_for(rel, all_files)
        if json_rel:
            result.json_map[rel] = json_rel
        else:
            result.no_json.append(rel)
        if ext not in WRITABLE_EXTS and ext not in SKIP_EXTS:
            result.skipped_formats[ext] = result.skipped_formats.get(ext, 0) + 1

    if progress_cb:
        progress_cb(total, total, "done")
    return result

"""
scanner.py — Recursive file and JSON discovery engine.
Builds a complete map of all media files and Google Takeout sidecar JSONs
in the given folder tree, regardless of folder structure.

JSON DETECTION STRATEGY — Content-based, not filename-based:
  Instead of matching filenames against a hardcoded list of known suffixes
  (which breaks whenever Google truncates differently), we cast a wide net:
  find every .json file, then peek inside to confirm it's a Google Takeout
  sidecar by checking for signature fields. This means NO suffix pattern can
  ever be missed — now or in the future.

  A file is identified as a Google Takeout sidecar if it contains at least
  one of these signature keys:
    - photoTakenTime
    - geoData
    - creationTime
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Union, Optional

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".jfif", ".heic", ".png",
    ".webp", ".mp4", ".mov", ".avi", ".mkv",
    ".gif", ".tiff", ".tif", ".bmp", ".3gp",
    ".m4v", ".wmv", ".flv", ".mts", ".m2ts"
}

PROGRESS_FILENAME = "._metadata_restore_progress.json"

# Signature fields that identify a Google Takeout sidecar JSON.
# If ANY of these keys are present in a .json file, it's a sidecar.
TAKEOUT_SIGNATURE_KEYS = {"photoTakenTime", "geoData", "creationTime"}

# Legacy constant — kept for compatibility with matcher.py references
JSON_SUFFIX = ".supplemental-metadata.json"


@dataclass
class ScanResult:
    """Holds the result of a full recursive scan."""
    # key: lowercase filename -> value: Path or list of Paths (if name collision)
    media_files: Dict[str, Union[Path, List[Path]]] = field(default_factory=dict)
    json_files: List[Path] = field(default_factory=list)
    total_media: int = 0
    total_json: int = 0
    root_folder: Path = None
    # Transparency stats
    json_candidates_checked: int = 0   # total .json files peeked at
    json_skipped_non_takeout: int = 0  # .json files that failed content check


def is_takeout_sidecar(filepath: Path) -> bool:
    """
    Peek inside a .json file and check for Google Takeout signature fields.
    Returns True if the file is a Takeout sidecar, False otherwise.
    Fast — reads only enough to find the keys, does not parse the full file.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
        return bool(TAKEOUT_SIGNATURE_KEYS & data.keys())
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, MemoryError):
        return False


def scan_folder(root: Union[str, Path], extra_extensions: set = None) -> ScanResult:
    """
    Recursively scan root folder for all media files and Google Takeout sidecar JSONs.

    JSON detection is content-based: every .json file is peeked at to confirm
    it contains Takeout signature fields. Truncated suffixes, unusual naming
    patterns, or any future Google export format changes are all handled
    automatically — no code changes ever needed.

    Returns a ScanResult. No hardcoded folder structure assumed.
    """
    root = Path(root)
    result = ScanResult(root_folder=root)

    extensions = SUPPORTED_EXTENSIONS.copy()
    if extra_extensions:
        extensions |= {
            ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
            for ext in extra_extensions
        }

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden system folders
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]

        for filename in filenames:
            filepath = Path(dirpath) / filename

            # Never process our own progress file
            if filename == PROGRESS_FILENAME:
                continue

            lower = filename.lower()
            suffix = Path(filename).suffix.lower()

            # ── JSON candidate: peek inside to confirm it's a Takeout sidecar ──
            if suffix == '.json':
                result.json_candidates_checked += 1
                if is_takeout_sidecar(filepath):
                    result.json_files.append(filepath)
                    result.total_json += 1
                else:
                    result.json_skipped_non_takeout += 1
                continue

            # ── Supported media file ──
            if suffix in extensions:
                if lower not in result.media_files:
                    result.media_files[lower] = filepath
                else:
                    # Collision: two files with same name in different folders
                    existing = result.media_files[lower]
                    if isinstance(existing, list):
                        existing.append(filepath)
                    else:
                        result.media_files[lower] = [existing, filepath]
                result.total_media += 1

    return result


def read_json_file(json_path: Path) -> Optional[dict]:
    """
    Safely read and parse a sidecar JSON file.
    Returns parsed dict or None on failure.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def get_media_title_from_json(data: dict) -> Optional[str]:
    """Extract the 'title' field from JSON — this is the original media filename."""
    return data.get("title") if data else None

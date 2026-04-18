"""
scanner.py — Recursive file and JSON discovery engine.
Builds a complete map of all media files and supplemental-metadata JSONs
in the given folder tree, regardless of folder structure.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Union

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".jfif", ".heic", ".png",
    ".webp", ".mp4", ".mov", ".avi", ".mkv",
    ".gif", ".tiff", ".tif", ".bmp", ".3gp",
    ".m4v", ".wmv", ".flv", ".mts", ".m2ts"
}

PROGRESS_FILENAME = "._metadata_restore_progress.json"
JSON_SUFFIX = ".supplemental-metadata.json"


@dataclass
class ScanResult:
    """Holds the result of a full recursive scan."""
    # key: lowercase filename → value: Path or list of Paths (if name collision across folders)
    media_files: Dict[str, Union[Path, List[Path]]] = field(default_factory=dict)
    json_files: List[Path] = field(default_factory=list)
    total_media: int = 0
    total_json: int = 0
    root_folder: Path = None


def scan_folder(root: Union[str, Path], extra_extensions: set = None) -> ScanResult:
    """
    Recursively scan root folder for all media files and supplemental-metadata JSONs.
    Returns a ScanResult with full maps — no hardcoded folder structure assumed.
    """
    root = Path(root)
    result = ScanResult(root_folder=root)

    extensions = SUPPORTED_EXTENSIONS.copy()
    if extra_extensions:
        extensions |= {ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
                       for ext in extra_extensions}

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden system folders
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]

        for filename in filenames:
            filepath = Path(dirpath) / filename

            # Never process our own progress file
            if filename == PROGRESS_FILENAME:
                continue

            lower = filename.lower()

            # Is it a supplemental-metadata JSON?
            if lower.endswith(JSON_SUFFIX.lower()):
                result.json_files.append(filepath)
                result.total_json += 1
                continue

            # Is it a supported media file?
            suffix = Path(filename).suffix.lower()
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


def read_json_file(json_path: Path) -> dict:
    """
    Safely read and parse a supplemental-metadata JSON file.
    Returns parsed dict or None on failure.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def get_media_title_from_json(data: dict) -> str:
    """Extract the 'title' field from JSON — this is the original media filename."""
    return data.get("title") if data else None

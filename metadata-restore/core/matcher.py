"""
matcher.py — JSON ↔ media file fuzzy matching engine.
Zero-skip policy: every JSON must be matched or escalated to review.
Never silently ignore anything.
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union
from core.scanner import ScanResult, read_json_file, get_media_title_from_json, JSON_SUFFIX


@dataclass
class MatchedPair:
    """A successfully matched JSON + media file pair."""
    json_path: Path
    media_path: Path
    json_data: dict
    match_method: str  # 'exact', 'title_field', 'fuzzy_truncated', 'fuzzy_numbered', 'fuzzy_extension'


@dataclass
class MatchResult:
    """Full result of the matching phase."""
    matched: List[MatchedPair] = field(default_factory=list)
    unmatched_jsons: List[Path] = field(default_factory=list)    # JSONs with no media found
    unreadable_jsons: List[Path] = field(default_factory=list)   # JSONs that failed to parse
    total_jsons: int = 0


def _stem_from_json_path(json_path: Path) -> str:
    """
    Extract the base media filename from the JSON sidecar filename.
    e.g. photo.jpg.supplemental-metadata.json → photo.jpg
         very_long_name.j.supplemental-metadata.json → very_long_name.j  (truncated)
    """
    name = json_path.name
    suffix = JSON_SUFFIX.lower()
    if name.lower().endswith(suffix):
        return name[: -len(suffix)]
    return name


def _try_match_exact(candidate: str, media_map: Dict) -> Optional[Path]:
    """Try exact case-insensitive match."""
    key = candidate.lower()
    result = media_map.get(key)
    if result:
        return result if isinstance(result, Path) else result[0]
    return None


def _try_match_truncated(candidate: str, media_map: Dict) -> Optional[Path]:
    """
    Google Takeout truncates filenames to ~47 chars before the extension in the JSON name.
    Try matching by checking if any media file starts with the candidate stem.
    e.g. candidate = "a_very_long_filename_that_got_tru.j"
         media     = "a_very_long_filename_that_got_truncated.jpeg"
    """
    # Split candidate into stem + ext
    cand_path = Path(candidate)
    cand_stem = cand_path.stem.lower()
    cand_ext = cand_path.suffix.lower()

    if len(cand_stem) < 5:
        return None  # Too short to safely fuzzy match

    for key, val in media_map.items():
        media_path = Path(key)
        media_stem = media_path.stem.lower()
        media_ext = media_path.suffix.lower()

        # Extension must be compatible (allow partial ext match too)
        ext_match = (
            media_ext == cand_ext or
            media_ext.startswith(cand_ext) or
            cand_ext.startswith(media_ext)
        )

        if ext_match and media_stem.startswith(cand_stem):
            return val if isinstance(val, Path) else val[0]

    return None


def _try_match_numbered(candidate: str, media_map: Dict) -> Optional[Path]:
    """
    Handle Google's numbered duplicate pattern.
    e.g. JSON title = "photo(1).jpg" but sidecar named "photo.jpg(1).supplemental-metadata.json"
    Also handles reverse cases.
    """
    # Try stripping/moving the (N) suffix
    pattern = re.compile(r'^(.*?)(\(\d+\))(\.\w+)$')
    m = pattern.match(candidate.lower())
    if m:
        base, num, ext = m.groups()
        # Try: base + ext (without number)
        alt1 = f"{base}{ext}"
        result = media_map.get(alt1)
        if result:
            return result if isinstance(result, Path) else result[0]
        # Try: base + num + ext (already tried as exact)

    return None


def _try_match_extension_variant(candidate: str, media_map: Dict) -> Optional[Path]:
    """
    Try matching with common extension variants.
    e.g. .jpg ↔ .jpeg, .jfif ↔ .jpg
    """
    ext_variants = {
        '.jpg': ['.jpeg', '.jfif'],
        '.jpeg': ['.jpg', '.jfif'],
        '.jfif': ['.jpg', '.jpeg'],
        '.tif': ['.tiff'],
        '.tiff': ['.tif'],
    }

    cand_path = Path(candidate.lower())
    stem = cand_path.stem
    ext = cand_path.suffix

    alternatives = ext_variants.get(ext, [])
    for alt_ext in alternatives:
        key = f"{stem}{alt_ext}"
        result = media_map.get(key)
        if result:
            return result if isinstance(result, Path) else result[0]

    return None


def _build_local_map(folder: Path, media_map: Dict) -> Dict:
    """
    Build a name→path map restricted to files in a specific folder.
    Used for Stage 0 same-folder preference matching.
    """
    local = {}
    for key, val in media_map.items():
        paths = val if isinstance(val, list) else [val]
        for p in paths:
            if p.parent == folder:
                local[key] = p
    return local


def _resolve_map_value(val) -> Optional[Path]:
    """Resolve a media_map value (Path or list[Path]) to a single Path."""
    if val is None:
        return None
    if isinstance(val, list):
        return val[0]
    return val


def match_all(scan_result: ScanResult) -> MatchResult:
    """
    Match every JSON sidecar to its media file using a multi-stage strategy.

    Stage 0: Same-folder exact match via title field (most reliable, avoids cross-folder collision)
    Stage 1: Global exact match via title field
    Stage 2: Global fuzzy match via title field (numbered variants, ext variants, truncation)
    Stage 3: Same-folder match via JSON filename stem
    Stage 4: Global fuzzy match via JSON filename stem
    Anything unmatched → review pile. Zero silent skips.
    """
    result = MatchResult(total_jsons=scan_result.total_json)
    media_map = scan_result.media_files

    for json_path in scan_result.json_files:
        json_data = read_json_file(json_path)

        if json_data is None:
            result.unreadable_jsons.append(json_path)
            continue

        media_path = None
        method = None
        json_folder = json_path.parent

        # Build a local map for same-folder preference
        local_map = _build_local_map(json_folder, media_map)

        title = get_media_title_from_json(json_data)

        # ── Stage 0: Same-folder exact match via title ──
        if title and local_map:
            media_path = _try_match_exact(title, local_map)
            if media_path:
                method = 'title_same_folder'

        # ── Stage 1: Global exact match via title ──
        if not media_path and title:
            media_path = _resolve_map_value(
                _try_match_exact(title, media_map)
            )
            if media_path:
                method = 'title_global'

        # ── Stage 2: Global fuzzy match via title ──
        if not media_path and title:
            media_path = _try_match_numbered(title, media_map)
            if media_path:
                method = 'fuzzy_numbered_title'

        if not media_path and title:
            media_path = _try_match_extension_variant(title, media_map)
            if media_path:
                method = 'fuzzy_extension_title'

        if not media_path and title:
            media_path = _try_match_truncated(title, media_map)
            if media_path:
                method = 'fuzzy_truncated_title'

        # ── Stage 3: Same-folder match via JSON filename stem ──
        if not media_path and local_map:
            candidate = _stem_from_json_path(json_path)
            media_path = _try_match_exact(candidate, local_map)
            if media_path:
                method = 'filename_same_folder'

            if not media_path:
                media_path = _try_match_numbered(candidate, local_map)
                if media_path:
                    method = 'fuzzy_numbered_filename_local'

            if not media_path:
                media_path = _try_match_extension_variant(candidate, local_map)
                if media_path:
                    method = 'fuzzy_extension_filename_local'

            if not media_path:
                media_path = _try_match_truncated(candidate, local_map)
                if media_path:
                    method = 'fuzzy_truncated_filename_local'

        # ── Stage 4: Global fuzzy match via JSON filename stem ──
        if not media_path:
            candidate = _stem_from_json_path(json_path)
            media_path = _try_match_numbered(candidate, media_map)
            if media_path:
                method = 'fuzzy_numbered_filename'

        if not media_path:
            candidate = _stem_from_json_path(json_path)
            media_path = _try_match_extension_variant(candidate, media_map)
            if media_path:
                method = 'fuzzy_extension_filename'

        if not media_path:
            candidate = _stem_from_json_path(json_path)
            media_path = _try_match_truncated(candidate, media_map)
            if media_path:
                method = 'fuzzy_truncated_filename'

        # ── Result ──
        if media_path:
            result.matched.append(MatchedPair(
                json_path=json_path,
                media_path=media_path,
                json_data=json_data,
                match_method=method
            ))
        else:
            result.unmatched_jsons.append(json_path)

    return result

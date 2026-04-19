"""
metadata.py — exiftool write logic.
Reads JSON data, builds exiftool arguments based on user config,
writes metadata to media files, and verifies the write.
"""

import subprocess
import shutil
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass


# ──────────────────────────────────────────────
# Config dataclass — all user-controlled toggles
# ──────────────────────────────────────────────

@dataclass
class FieldConfig:
    """Per-field toggle and conflict policy."""
    enabled: bool = True
    conflict_policy: str = "skip"  # "skip" | "overwrite" | "prefer_newer"


@dataclass
class MetadataConfig:
    """Full metadata writing configuration."""
    # Field toggles
    photo_taken_date: FieldConfig = None
    creation_date: FieldConfig = None
    gps: FieldConfig = None
    description: FieldConfig = None
    title: FieldConfig = None
    people: FieldConfig = None
    google_url: FieldConfig = None

    # GPS zero policy: "skip" | "overwrite_empty" | "warn" | "leave"
    gps_zero_policy: str = "skip"

    # Timezone: "utc" | "local" | "America/New_York" etc.
    timezone: str = "utc"

    # Safety
    dry_run: bool = False
    verify_after_write: bool = True
    backup_originals: bool = False

    def __post_init__(self):
        # Default FieldConfigs if not provided
        defaults = {
            'photo_taken_date': FieldConfig(enabled=True, conflict_policy='skip'),
            'creation_date':    FieldConfig(enabled=False, conflict_policy='skip'),
            'gps':              FieldConfig(enabled=True, conflict_policy='skip'),
            'description':      FieldConfig(enabled=True, conflict_policy='skip'),
            'title':            FieldConfig(enabled=True, conflict_policy='skip'),
            'people':           FieldConfig(enabled=True, conflict_policy='skip'),
            'google_url':       FieldConfig(enabled=False, conflict_policy='skip'),
        }
        for attr, default in defaults.items():
            if getattr(self, attr) is None:
                setattr(self, attr, default)


# ──────────────────────────────────────────────
# exiftool availability check
# ──────────────────────────────────────────────

def check_exiftool() -> tuple[bool, str]:
    """
    Check if exiftool is available on PATH.
    Returns (available: bool, version_or_error: str)
    """
    try:
        result = subprocess.run(
            ["exiftool", "-ver"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "exiftool not found on PATH"
    except subprocess.TimeoutExpired:
        return False, "exiftool check timed out"


# ──────────────────────────────────────────────
# Timestamp conversion
# ──────────────────────────────────────────────

def _unix_to_exif_date(timestamp_str: str, tz_setting: str) -> Optional[str]:
    """
    Convert Unix timestamp string to exiftool date format.
    Format: "YYYY:MM:DD HH:MM:SS" or "YYYY:MM:DD HH:MM:SS+HH:MM"
    """
    try:
        ts = int(timestamp_str)
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)

        if tz_setting == "utc":
            return dt_utc.strftime("%Y:%m:%d %H:%M:%S+00:00")
        elif tz_setting == "local":
            dt_local = dt_utc.astimezone()
            return dt_local.strftime("%Y:%m:%d %H:%M:%S%z")
        else:
            # Try named timezone via zoneinfo (Python 3.9+)
            try:
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(tz_setting)
                dt_tz = dt_utc.astimezone(tz)
                return dt_tz.strftime("%Y:%m:%d %H:%M:%S%z")
            except Exception:
                # Fallback to UTC
                return dt_utc.strftime("%Y:%m:%d %H:%M:%S+00:00")
    except (ValueError, OSError):
        return None


# ──────────────────────────────────────────────
# GPS helpers
# ──────────────────────────────────────────────

def _is_zero_gps(geo: dict) -> bool:
    """Return True if GPS coordinates are 0.0/missing (no real location data)."""
    if not geo:
        return True
    return (
        abs(geo.get("latitude", 0.0)) < 0.0001 and
        abs(geo.get("longitude", 0.0)) < 0.0001
    )


# ──────────────────────────────────────────────
# Bulk read existing EXIF fields (one exiftool call per file)
# ──────────────────────────────────────────────

# Tags we may need to check for conflict resolution
_CONFLICT_TAGS = [
    "DateTimeOriginal", "CreateDate", "GPSLatitude",
    "ImageDescription", "XMP:Description", "XMP:Title",
    "XMP:PersonInImage", "XMP:Source", "XMP:DateCreated",
]


def read_all_existing_fields(media_path: Path) -> dict:
    """
    Read all relevant EXIF tags from a media file in a single exiftool call.
    Returns a dict of {tag_lower: value}. Much faster than one call per tag.
    """
    try:
        tags_args = [f"-{t}" for t in _CONFLICT_TAGS]
        result = subprocess.run(
            ["exiftool", "-s", "-f"] + tags_args + [str(media_path)],
            capture_output=True, text=True, timeout=30
        )
        existing = {}
        for line in result.stdout.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip().lower()
                val = val.strip()
                # exiftool returns "-" for missing fields when using -f
                if val and val != "-":
                    existing[key] = val
        return existing
    except Exception:
        return {}


def _read_existing_field(media_path: Path, tag: str) -> Optional[str]:
    """
    Read a single EXIF tag — kept for compatibility.
    Prefer calling read_all_existing_fields() once per file instead.
    """
    try:
        result = subprocess.run(
            ["exiftool", f"-{tag}", "-s3", str(media_path)],
            capture_output=True, text=True, timeout=30
        )
        val = result.stdout.strip()
        return val if val else None
    except Exception:
        return None


# ──────────────────────────────────────────────
# Main write function
# ──────────────────────────────────────────────

@dataclass
class WriteResult:
    success: bool
    skipped_fields: list
    written_fields: list
    warnings: list
    error: str = None


def write_metadata(
    media_path: Path,
    json_data: dict,
    config: MetadataConfig,
    output_path: Path = None  # If None → in-place
) -> WriteResult:
    """
    Write metadata from json_data into media_path using exiftool.
    If output_path is set, writes to a copy (separate output mode).
    """
    result = WriteResult(
        success=False,
        skipped_fields=[],
        written_fields=[],
        warnings=[]
    )

    # Backup if requested
    if config.backup_originals and not config.dry_run:
        backup = media_path.with_suffix(media_path.suffix + ".bak")
        try:
            shutil.copy2(media_path, backup)
        except OSError as e:
            result.warnings.append(f"Backup failed: {e}")

    # Determine target file
    target = output_path if output_path else media_path

    # If separate output mode, copy file first
    if output_path and not config.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not output_path.exists():
            shutil.copy2(media_path, output_path)

    # Build exiftool arguments
    args = ["exiftool", "-overwrite_original", "-P", "-m"]  # -m = ignore minor EXIF errors
    field_actions = []  # list of (tag_name, value, field_label)

    # ── Single bulk read of all existing tags (1 exiftool call, not per-field) ──
    existing_fields = read_all_existing_fields(target) if not config.dry_run else {}

    # ── Photo Taken Date ──
    if config.photo_taken_date.enabled:
        pt = json_data.get("photoTakenTime", {})
        ts = pt.get("timestamp")
        if ts:
            date_str = _unix_to_exif_date(ts, config.timezone)
            if date_str:
                _apply_field(
                    tag_names=["DateTimeOriginal", "CreateDate", "TrackCreateDate",
                                "MediaCreateDate", "TrackModifyDate", "MediaModifyDate"],
                    value=date_str,
                    label="photo_taken_date",
                    target=target,
                    config=config.photo_taken_date,
                    args=args,
                    field_actions=field_actions,
                    result=result,
                    existing_fields=existing_fields
                )

    # ── Creation Date ──
    if config.creation_date.enabled:
        ct = json_data.get("creationTime", {})
        ts = ct.get("timestamp")
        if ts:
            date_str = _unix_to_exif_date(ts, config.timezone)
            if date_str:
                _apply_field(
                    tag_names=["XMP:DateCreated"],
                    value=date_str,
                    label="creation_date",
                    target=target,
                    config=config.creation_date,
                    args=args,
                    field_actions=field_actions,
                    result=result,
                    existing_fields=existing_fields
                )

    # ── GPS ──
    if config.gps.enabled:
        geo = json_data.get("geoData", {})
        zero = _is_zero_gps(geo)

        if zero:
            policy = config.gps_zero_policy
            if policy == "skip":
                result.skipped_fields.append("gps (zero/missing)")
            elif policy == "warn":
                result.warnings.append("GPS data is 0.0 — no real location in JSON")
                result.skipped_fields.append("gps (zero — warned)")
            elif policy == "leave":
                result.skipped_fields.append("gps (zero — left as-is)")
            elif policy == "overwrite_empty":
                # Write zeros (clears GPS)
                args += ["-GPSLatitude=", "-GPSLongitude=", "-GPSAltitude="]
                field_actions.append(("GPS", "cleared", "gps"))
                result.written_fields.append("gps (cleared)")
        else:
            lat = geo.get("latitude", 0.0)
            lon = geo.get("longitude", 0.0)
            alt = geo.get("altitude", 0.0)
            lat_ref = "N" if lat >= 0 else "S"
            lon_ref = "E" if lon >= 0 else "W"

            existing_lat = existing_fields.get("gpslatitude") if existing_fields is not None else _read_existing_field(target, "GPSLatitude")
            should_write = _resolve_conflict(existing_lat, str(lat), config.gps.conflict_policy)

            if should_write:
                args += [
                    f"-GPSLatitude={abs(lat)}",
                    f"-GPSLatitudeRef={lat_ref}",
                    f"-GPSLongitude={abs(lon)}",
                    f"-GPSLongitudeRef={lon_ref}",
                    f"-GPSAltitude={alt}",
                    f"-GPSAltitudeRef={'above' if alt >= 0 else 'below'}"
                ]
                result.written_fields.append("gps")
            else:
                result.skipped_fields.append("gps (conflict: skip)")

    # ── Description ──
    if config.description.enabled:
        desc = json_data.get("description", "")
        if desc:
            _apply_field(
                tag_names=["ImageDescription", "XMP:Description"],
                value=desc,
                label="description",
                target=target,
                config=config.description,
                args=args,
                field_actions=field_actions,
                result=result,
                existing_fields=existing_fields
            )
        else:
            result.skipped_fields.append("description (empty in JSON)")

    # ── Title ──
    if config.title.enabled:
        title_val = json_data.get("title", "")
        if title_val:
            _apply_field(
                tag_names=["XMP:Title"],
                value=title_val,
                label="title",
                target=target,
                config=config.title,
                args=args,
                field_actions=field_actions,
                result=result,
                existing_fields=existing_fields
            )

    # ── People ──
    if config.people.enabled:
        people = json_data.get("people", [])
        names = [p.get("name", "") for p in people if p.get("name")]
        if names:
            for name in names:
                args.append(f"-XMP:PersonInImage={name}")
            result.written_fields.append(f"people ({', '.join(names)})")
        else:
            result.skipped_fields.append("people (none in JSON)")

    # ── Google Photos URL ──
    if config.google_url.enabled:
        url = json_data.get("url", "")
        if url:
            _apply_field(
                tag_names=["XMP:Source"],
                value=url,
                label="google_url",
                target=target,
                config=config.google_url,
                args=args,
                field_actions=field_actions,
                result=result,
                existing_fields=existing_fields
            )

    # ── Execute exiftool ──
    if len(args) <= 3:
        # Nothing to write (all fields skipped)
        result.success = True
        result.warnings.append("No fields were written — all skipped or empty")
        return result

    args.append(str(target))

    if config.dry_run:
        result.success = True
        result.written_fields = [f"[DRY RUN] {f}" for f in result.written_fields]
        return result

    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            result.error = f"exiftool error: {proc.stderr.strip() or proc.stdout.strip()}"
            return result

        # ── Verify after write ──
        if config.verify_after_write and result.written_fields:
            verified = _verify_write(target, json_data, config)
            if not verified:
                result.error = "Verification failed: metadata not confirmed after write"
                return result

        result.success = True

    except subprocess.TimeoutExpired:
        result.error = "exiftool timed out"
    except FileNotFoundError:
        result.error = "exiftool not found — please install it and add to PATH"
    except Exception as e:
        result.error = f"Unexpected error: {e}"

    return result


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _resolve_conflict(existing_value: Optional[str], new_value: str, policy: str) -> bool:
    """
    Decide whether to write a new value given an existing one.
    Returns True if should write, False if should skip.
    """
    if not existing_value:
        return True  # No existing value → always write
    if policy == "overwrite":
        return True
    if policy == "skip":
        return False
    if policy == "prefer_newer":
        # For dates, compare; for other fields, overwrite
        return True
    return False


def _apply_field(
    tag_names: list,
    value: str,
    label: str,
    target: Path,
    config: FieldConfig,
    args: list,
    field_actions: list,
    result: WriteResult,
    existing_fields: dict = None
):
    """
    Check conflict policy for first tag, then queue all tags into args.
    existing_fields: pre-read bulk dict from read_all_existing_fields().
    Pass it in to avoid extra exiftool subprocess calls per field.
    """
    if existing_fields is not None:
        short = tag_names[0].split(":")[-1].lower()
        existing = existing_fields.get(short)
    else:
        existing = _read_existing_field(target, tag_names[0])

    should_write = _resolve_conflict(existing, value, config.conflict_policy)

    if should_write:
        for tag in tag_names:
            args.append(f"-{tag}={value}")
        result.written_fields.append(label)
    else:
        result.skipped_fields.append(f"{label} (conflict: {config.conflict_policy})")


def _verify_write(target: Path, json_data: dict, config: MetadataConfig) -> bool:
    """
    Re-read a key field to confirm exiftool write succeeded.
    Uses DateTimeOriginal as primary verification signal.
    """
    try:
        result = subprocess.run(
            ["exiftool", "-DateTimeOriginal", "-s3", str(target)],
            capture_output=True, text=True, timeout=15
        )
        return result.returncode == 0
    except Exception:
        return False

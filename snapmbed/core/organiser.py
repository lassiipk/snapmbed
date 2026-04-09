"""
SnapMbed — Organiser
Handles date-based folder organisation and filename sanitisation.
"""

import os
import re
import shutil
import datetime

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


def organised_path(ts_str, orig_rel_path, structure, tz_offset=0):
    """
    Build a new relative path for a file based on its timestamp.
    structure: 'year' | 'year-month' | 'year-month-day'
    Returns new relative path string.
    """
    filename = os.path.basename(orig_rel_path)
    if not ts_str:
        return os.path.join("undated", filename)

    ts = int(ts_str)
    dt = datetime.datetime.utcfromtimestamp(ts) + datetime.timedelta(hours=tz_offset)
    yr  = str(dt.year)
    mo  = f"{dt.month:02d} - {MONTHS[dt.month - 1]}"
    dy  = f"{dt.day:02d}"

    if structure == "year":
        return os.path.join(yr, filename)
    elif structure == "year-month":
        return os.path.join(yr, mo, filename)
    else:  # year-month-day
        return os.path.join(yr, mo, dy, filename)


def sanitise_filename(orig_name, ts_str, counter, tz_offset=0):
    """
    Replace cryptic filenames with date-based names.
    e.g. AF1Qip_abc123.jpg → 2024-03-15_001.jpg
    Returns new filename (not full path).
    """
    _, ext = os.path.splitext(orig_name)

    # Only sanitise if the original looks cryptic (no date pattern)
    date_pattern = re.compile(r'\d{4}[-_]\d{2}[-_]\d{2}')
    if date_pattern.search(orig_name):
        return orig_name  # Already has a date, leave it

    if ts_str:
        ts = int(ts_str)
        dt = datetime.datetime.utcfromtimestamp(ts) + datetime.timedelta(hours=tz_offset)
        return f"{dt.strftime('%Y-%m-%d')}_{counter:03d}{ext.lower()}"
    else:
        return f"undated_{counter:03d}{ext.lower()}"


def move_file(src_abs, dest_abs, dry_run=False):
    """Move src to dest, creating directories as needed."""
    if dry_run:
        return True
    os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
    shutil.move(src_abs, dest_abs)
    return True


def rename_file(src_abs, new_name, dry_run=False):
    """Rename a file in-place."""
    dest_abs = os.path.join(os.path.dirname(src_abs), new_name)
    if src_abs == dest_abs:
        return dest_abs
    if dry_run:
        return dest_abs
    if os.path.exists(dest_abs):
        # Don't overwrite — append counter suffix
        base, ext = os.path.splitext(new_name)
        i = 1
        while os.path.exists(dest_abs):
            dest_abs = os.path.join(os.path.dirname(src_abs), f"{base}_{i:02d}{ext}")
            i += 1
    os.rename(src_abs, dest_abs)
    return dest_abs

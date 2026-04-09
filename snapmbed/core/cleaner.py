"""
SnapMbed — Cleaner & State
Deletes JSON sidecar files after successful processing.
Manages resume state so interrupted runs can continue.
"""

import os
import json
import hashlib


STATE_FILENAME = ".snapmbed_state.json"


# ─────────────────────────────────────────────────────────────
#  JSON sidecar deletion
# ─────────────────────────────────────────────────────────────

def delete_sidecar(json_abs_path, dry_run=False):
    """
    Delete a JSON sidecar file after successful embedding.
    Returns True on success, False on failure.
    """
    if dry_run:
        return True
    try:
        if os.path.exists(json_abs_path):
            os.remove(json_abs_path)
            return True
        return False
    except Exception:
        return False


def delete_empty_dirs(folder_path, dry_run=False):
    """
    After processing, remove any directories that are now empty
    (e.g. a year folder that only contained JSON files).
    """
    deleted = []
    for root, dirs, files in os.walk(folder_path, topdown=False):
        if root == folder_path:
            continue
        if not os.listdir(root):
            if not dry_run:
                try:
                    os.rmdir(root)
                    deleted.append(root)
                except Exception:
                    pass
            else:
                deleted.append(root)
    return deleted


# ─────────────────────────────────────────────────────────────
#  Resume state
# ─────────────────────────────────────────────────────────────

def _state_path(folder_path):
    return os.path.join(folder_path, STATE_FILENAME)


def load_state(folder_path):
    """Load previously processed file set from state file."""
    path = _state_path(folder_path)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("processed", []))
    except Exception:
        return set()


def save_state(folder_path, processed_set):
    """Save the set of processed file paths to state file."""
    path = _state_path(folder_path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"processed": list(processed_set)}, f, indent=2)
    except Exception:
        pass


def clear_state(folder_path):
    """Delete the state file (full reset)."""
    path = _state_path(folder_path)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass

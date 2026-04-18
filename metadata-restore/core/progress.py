"""
progress.py — Resume/progress tracking.
Writes a ._metadata_restore_progress.json inside the processed folder.
Tracks which files have been processed so interrupted runs can resume.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, Set

PROGRESS_FILENAME = "._metadata_restore_progress.json"


@dataclass
class SessionStats:
    started_at: str = ""
    last_updated: str = ""
    total_json_found: int = 0
    processed: int = 0
    skipped_already_done: int = 0
    failed: int = 0
    json_deleted: int = 0
    unmatched_json: int = 0


@dataclass
class ProgressState:
    session_stats: SessionStats = field(default_factory=SessionStats)
    completed: Dict[str, str] = field(default_factory=dict)   # media_path_str → "ok" | "failed"
    failed_files: Dict[str, str] = field(default_factory=dict) # media_path_str → error message


class ProgressTracker:
    def __init__(self, root_folder: Path):
        self.root_folder = Path(root_folder)
        self.progress_file = self.root_folder / PROGRESS_FILENAME
        self.state = ProgressState()
        self._load()

    def _load(self):
        """Load existing progress file if it exists."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                stats = data.get("session_stats", {})
                self.state.session_stats = SessionStats(**{
                    k: v for k, v in stats.items()
                    if k in SessionStats.__dataclass_fields__
                })
                self.state.completed = data.get("completed", {})
                self.state.failed_files = data.get("failed_files", {})
            except (json.JSONDecodeError, OSError, TypeError):
                # Corrupt progress file — start fresh
                self.state = ProgressState()

    def _save(self):
        """Persist progress to disk."""
        self.state.session_stats.last_updated = _now()
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "session_stats": asdict(self.state.session_stats),
                    "completed": self.state.completed,
                    "failed_files": self.state.failed_files,
                }, f, indent=2)
        except OSError:
            pass  # Non-fatal — progress just won't be saved

    def start_session(self, total_json: int):
        """Initialize a new session (or continue existing)."""
        if not self.state.session_stats.started_at:
            self.state.session_stats.started_at = _now()
        self.state.session_stats.total_json_found = total_json
        self._save()

    def is_completed(self, media_path: Path) -> bool:
        """Check if a media file was already successfully processed."""
        return str(media_path) in self.state.completed and \
               self.state.completed[str(media_path)] == "ok"

    def mark_success(self, media_path: Path):
        self.state.completed[str(media_path)] = "ok"
        self.state.session_stats.processed += 1
        self._save()

    def mark_failed(self, media_path: Path, error: str):
        self.state.completed[str(media_path)] = "failed"
        self.state.failed_files[str(media_path)] = error
        self.state.session_stats.failed += 1
        self._save()

    def mark_skipped(self):
        self.state.session_stats.skipped_already_done += 1
        self._save()

    def mark_json_deleted(self):
        self.state.session_stats.json_deleted += 1
        self._save()

    def mark_unmatched(self, count: int = 1):
        self.state.session_stats.unmatched_json += count
        self._save()

    def get_stats(self) -> SessionStats:
        return self.state.session_stats

    def get_failed_files(self) -> Dict[str, str]:
        return self.state.failed_files

    def clear(self):
        """Delete the progress file (user-requested cleanup)."""
        try:
            if self.progress_file.exists():
                self.progress_file.unlink()
        except OSError:
            pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

"""
reporter.py — Logging, audit trail, and summary report generation.
Writes timestamped log files and a clean failed_files.txt.
"""

import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional


class Reporter:
    """
    Handles all logging and reporting for a run.
    Writes to a timestamped log file and optionally streams to a callback
    (for GUI live log display or CLI stdout).
    """

    def __init__(self, log_dir: Path, stream_callback: Optional[Callable] = None):
        """
        log_dir: where to write log files (typically the script directory)
        stream_callback: optional function(str) called for each log line (GUI/CLI live feed)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.stream_callback = stream_callback

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = self.log_dir / f"metadata_restore_{timestamp}.log"
        self.failed_path = self.log_dir / f"failed_files_{timestamp}.txt"

        self._failed_entries = []
        self._setup_logger()

    def _setup_logger(self):
        self.logger = logging.getLogger(f"metadata_restore_{id(self)}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # File handler
        fh = logging.FileHandler(self.log_path, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        self.logger.addHandler(fh)

    def _emit(self, level: str, msg: str):
        getattr(self.logger, level)(msg)
        if self.stream_callback:
            try:
                self.stream_callback(f"[{level.upper()}] {msg}")
            except Exception:
                pass

    def info(self, msg: str):
        self._emit("info", msg)

    def warning(self, msg: str):
        self._emit("warning", msg)

    def error(self, msg: str):
        self._emit("error", msg)

    def debug(self, msg: str):
        self._emit("debug", msg)

    def success(self, msg: str):
        """Log a success message (mapped to INFO with SUCCESS prefix)."""
        self._emit("info", f"✓ {msg}")

    def log_match(self, json_path: Path, media_path: Path, method: str):
        self.debug(f"MATCH [{method}] {json_path.name} → {media_path.name}")

    def log_unmatched(self, json_path: Path):
        self.warning(f"UNMATCHED JSON: {json_path}")

    def log_write_result(self, media_path: Path, written: list, skipped: list,
                         warnings: list, error: str = None):
        if error:
            self.error(f"WRITE FAILED: {media_path} | Error: {error}")
            self._failed_entries.append((str(media_path), error))
        else:
            parts = []
            if written:
                parts.append(f"wrote={','.join(written)}")
            if skipped:
                parts.append(f"skipped={','.join(skipped)}")
            if warnings:
                parts.append(f"warnings={';'.join(warnings)}")
            self.success(f"WROTE: {media_path.name} | {' | '.join(parts)}")

    def log_json_deleted(self, json_path: Path):
        self.info(f"DELETED JSON: {json_path.name}")

    def log_json_kept(self, json_path: Path, reason: str):
        self.info(f"KEPT JSON ({reason}): {json_path.name}")

    def log_json_moved(self, json_path: Path, dest: Path):
        self.info(f"MOVED JSON: {json_path.name} → {dest}")

    def log_skipped_already_done(self, media_path: Path):
        self.debug(f"SKIP (already processed): {media_path.name}")

    def write_failed_files(self):
        """Write a clean list of all failed files for manual follow-up."""
        if not self._failed_entries:
            return
        try:
            with open(self.failed_path, 'w', encoding='utf-8') as f:
                f.write("# Files that failed metadata writing\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                for path, error in self._failed_entries:
                    f.write(f"{path}\n  Error: {error}\n\n")
        except OSError:
            pass

    def print_summary(self, stats, unmatched_count: int = 0):
        """Log and return the final summary string."""
        lines = [
            "",
            "═" * 55,
            "  METADATA RESTORE — COMPLETE",
            "═" * 55,
            f"  Total media found    : {stats.total_json_found}",
            f"  ✓ Successfully done  : {stats.processed}",
            f"  ↩ Already processed  : {stats.skipped_already_done}",
            f"  ✗ Failed             : {stats.failed}",
            f"  🗑 JSONs deleted      : {stats.json_deleted}",
            f"  ⚠ Unmatched JSONs    : {unmatched_count}",
            "─" * 55,
            f"  Log file : {self.log_path.name}",
        ]
        if self._failed_entries:
            lines.append(f"  Failures : {self.failed_path.name}")
        lines.append("═" * 55)

        summary = "\n".join(lines)
        for line in lines:
            self.info(line)

        self.write_failed_files()
        return summary

    @property
    def log_file_path(self) -> Path:
        return self.log_path

    @property
    def failed_file_path(self) -> Path:
        return self.failed_path

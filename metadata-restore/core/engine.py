"""
engine.py — Main processing pipeline.
Orchestrates: scan → match → write → delete → report.
Used by both CLI and GUI interfaces.
"""

import shutil
from pathlib import Path
from typing import Callable, Optional

from core.scanner import scan_folder
from core.matcher import match_all
from core.metadata import MetadataConfig, write_metadata, check_exiftool
from core.progress import ProgressTracker
from core.reporter import Reporter


class RunConfig:
    """All options for a single run."""

    def __init__(self):
        # Paths
        self.source_folder: str = ""
        self.output_folder: str = ""          # Empty = in-place
        self.output_mode: str = "inplace"     # "inplace" | "separate"

        # Metadata config
        self.metadata: MetadataConfig = MetadataConfig()

        # Behaviour
        self.dry_run: bool = False
        self.force_reprocess: bool = False
        self.cleanup_progress_file: bool = False

        # Unmatched JSONs policy
        self.unmatched_policy: str = "keep"   # "keep" | "move" | "delete"

        # Extra extensions (user-added beyond defaults)
        self.extra_extensions: set = set()

    def to_dict(self) -> dict:
        """Serialize for config file saving."""
        import dataclasses
        return {
            "source_folder": self.source_folder,
            "output_folder": self.output_folder,
            "output_mode": self.output_mode,
            "dry_run": self.dry_run,
            "force_reprocess": self.force_reprocess,
            "unmatched_policy": self.unmatched_policy,
            "gps_zero_policy": self.metadata.gps_zero_policy,
            "timezone": self.metadata.timezone,
            "backup_originals": self.metadata.backup_originals,
            "verify_after_write": self.metadata.verify_after_write,
            "fields": {
                name: {
                    "enabled": getattr(self.metadata, name).enabled,
                    "conflict_policy": getattr(self.metadata, name).conflict_policy
                }
                for name in ["photo_taken_date", "creation_date", "gps",
                             "description", "title", "people", "google_url"]
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunConfig":
        """Deserialize from config file."""
        from core.metadata import FieldConfig
        cfg = cls()
        cfg.source_folder = data.get("source_folder", "")
        cfg.output_folder = data.get("output_folder", "")
        cfg.output_mode = data.get("output_mode", "inplace")
        cfg.dry_run = data.get("dry_run", False)
        cfg.force_reprocess = data.get("force_reprocess", False)
        cfg.unmatched_policy = data.get("unmatched_policy", "keep")
        cfg.metadata.gps_zero_policy = data.get("gps_zero_policy", "skip")
        cfg.metadata.timezone = data.get("timezone", "utc")
        cfg.metadata.backup_originals = data.get("backup_originals", False)
        cfg.metadata.verify_after_write = data.get("verify_after_write", True)

        for name, vals in data.get("fields", {}).items():
            if hasattr(cfg.metadata, name):
                fc = FieldConfig(
                    enabled=vals.get("enabled", True),
                    conflict_policy=vals.get("conflict_policy", "skip")
                )
                setattr(cfg.metadata, name, fc)

        return cfg


class Engine:
    """
    Runs the full metadata restoration pipeline.
    Accepts callbacks for progress updates (used by GUI and CLI progress bars).
    """

    def __init__(
        self,
        config: RunConfig,
        log_dir: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        stop_flag: Optional[Callable[[], bool]] = None
    ):
        """
        progress_callback(current, total, status_msg): called after each file
        log_callback(message): called for each log line
        stop_flag(): returns True if user requested stop
        """
        self.config = config
        self.log_dir = Path(log_dir)
        self.progress_callback = progress_callback or (lambda c, t, m: None)
        self.stop_flag = stop_flag or (lambda: False)
        self.reporter = Reporter(log_dir, stream_callback=log_callback)

    def run(self) -> dict:
        """
        Execute the full pipeline. Returns summary dict.
        """
        cfg = self.config
        r = self.reporter
        source = Path(cfg.source_folder)

        r.info("=" * 55)
        r.info("METADATA RESTORE — STARTING")
        r.info(f"Source     : {source}")
        r.info(f"Mode       : {'DRY RUN' if cfg.dry_run else cfg.output_mode.upper()}")
        r.info("=" * 55)

        # ── 1. Scan ──
        r.info("Phase 1: Scanning folder tree...")
        self.progress_callback(0, 1, "Scanning folder tree...")
        scan = scan_folder(source, cfg.extra_extensions)
        r.info(f"  Found {scan.total_media} media files, {scan.total_json} JSON sidecars")

        if scan.total_json == 0:
            r.warning("No supplemental-metadata.json files found. Nothing to do.")
            return {"status": "nothing_to_do"}

        # ── 2. Match ──
        r.info("Phase 2: Matching JSONs to media files...")
        self.progress_callback(0, 1, "Matching JSON files to media...")
        match_result = match_all(scan)
        r.info(f"  Matched  : {len(match_result.matched)}")
        r.info(f"  Unmatched: {len(match_result.unmatched_jsons)}")
        r.info(f"  Unreadable JSONs: {len(match_result.unreadable_jsons)}")

        for pair in match_result.matched:
            r.log_match(pair.json_path, pair.media_path, pair.match_method)
        for jp in match_result.unmatched_jsons:
            r.log_unmatched(jp)

        # ── 3. Progress tracker ──
        tracker = ProgressTracker(source)
        tracker.start_session(scan.total_json)

        # ── 4. Process matched pairs ──
        r.info("Phase 3: Writing metadata...")
        total = len(match_result.matched)

        for i, pair in enumerate(match_result.matched):
            if self.stop_flag():
                r.warning("STOPPED by user request.")
                break

            media = pair.media_path
            status_msg = f"Processing: {media.name}"
            self.progress_callback(i, total, status_msg)

            # Skip if already done and not forcing reprocess
            if not cfg.force_reprocess and tracker.is_completed(media):
                r.log_skipped_already_done(media)
                tracker.mark_skipped()
                continue

            # Determine output path
            output_path = None
            if cfg.output_mode == "separate" and cfg.output_folder:
                rel = media.relative_to(source)
                output_path = Path(cfg.output_folder) / rel

            # Write metadata
            write_result = write_metadata(
                media_path=media,
                json_data=pair.json_data,
                config=cfg.metadata,
                output_path=output_path
            )

            r.log_write_result(
                media_path=media,
                written=write_result.written_fields,
                skipped=write_result.skipped_fields,
                warnings=write_result.warnings,
                error=write_result.error
            )

            if write_result.success:
                tracker.mark_success(media)
                # Delete JSON (only after verified success, not in dry run)
                if not cfg.dry_run:
                    _safe_delete_json(pair.json_path, tracker, r)
            else:
                tracker.mark_failed(media, write_result.error or "unknown error")

        self.progress_callback(total, total, "Writing complete.")

        # ── 5. Handle unmatched JSONs ──
        unmatched = match_result.unmatched_jsons + match_result.unreadable_jsons
        if unmatched:
            r.info(f"Phase 4: Handling {len(unmatched)} unmatched/unreadable JSONs...")
            _handle_unmatched(unmatched, cfg, source, tracker, r)
        tracker.mark_unmatched(len(unmatched))

        # ── 6. Summary ──
        stats = tracker.get_stats()
        summary = r.print_summary(stats, unmatched_count=len(unmatched))
        self.progress_callback(total, total, "Done.")

        # ── 7. Cleanup progress file ──
        if cfg.cleanup_progress_file and not cfg.dry_run:
            tracker.clear()

        return {
            "status": "done",
            "summary": summary,
            "stats": stats,
            "log_path": str(r.log_file_path),
            "failed_path": str(r.failed_file_path) if tracker.get_failed_files() else None,
        }


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _safe_delete_json(json_path: Path, tracker: ProgressTracker, r: Reporter):
    """Delete a JSON sidecar file safely."""
    try:
        json_path.unlink()
        tracker.mark_json_deleted()
        r.log_json_deleted(json_path)
    except OSError as e:
        r.error(f"Could not delete JSON {json_path.name}: {e}")


def _handle_unmatched(
    json_paths: list,
    cfg: RunConfig,
    source: Path,
    tracker: ProgressTracker,
    r: Reporter
):
    """Apply the user's unmatched JSON policy."""
    policy = cfg.unmatched_policy

    for jp in json_paths:
        if policy == "keep":
            r.log_json_kept(jp, "unmatched — kept in place")

        elif policy == "move":
            if not cfg.dry_run:
                review_dir = source / "_unmatched_review"
                review_dir.mkdir(exist_ok=True)
                dest = review_dir / jp.name
                # Handle name collision in review folder
                counter = 1
                while dest.exists():
                    dest = review_dir / f"{jp.stem}_{counter}{jp.suffix}"
                    counter += 1
                try:
                    shutil.move(str(jp), dest)
                    r.log_json_moved(jp, dest)
                except OSError as e:
                    r.error(f"Could not move {jp.name}: {e}")
            else:
                r.info(f"[DRY RUN] Would move: {jp.name} → _unmatched_review/")

        elif policy == "delete":
            if not cfg.dry_run:
                try:
                    jp.unlink()
                    r.info(f"DELETED unmatched JSON: {jp.name}")
                except OSError as e:
                    r.error(f"Could not delete {jp.name}: {e}")
            else:
                r.info(f"[DRY RUN] Would delete unmatched: {jp.name}")

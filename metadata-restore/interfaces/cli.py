"""
cli.py — Command-line interface for the metadata restore tool.
Full argparse-based interface with progress bar via tqdm.
"""

import sys
import argparse
import json
from pathlib import Path

# Try tqdm for a nice progress bar; fall back to simple counter
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

from core.engine import Engine, RunConfig
from core.metadata import MetadataConfig, FieldConfig, check_exiftool


FIELD_NAMES = ["photo_taken_date", "creation_date", "gps",
               "description", "title", "people", "google_url"]

CONFLICT_CHOICES = ["skip", "overwrite", "prefer_newer"]
GPS_ZERO_CHOICES = ["skip", "overwrite_empty", "warn", "leave"]
UNMATCHED_CHOICES = ["keep", "move", "delete"]
OUTPUT_CHOICES   = ["inplace", "separate"]
TIMEZONE_CHOICES = ["utc", "local"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="metadata-restore",
        description="Google Takeout Metadata Restore Tool — bake JSON metadata into media files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  # Dry run — see what would happen
  python main.py --cli --source "C:/Takeout" --dry-run

  # In-place with defaults
  python main.py --cli --source "C:/Takeout"

  # Separate output folder
  python main.py --cli --source "C:/Takeout" --output "C:/Takeout_fixed" --output-mode separate

  # Overwrite all existing dates
  python main.py --cli --source "C:/Takeout" --conflict-photo-date overwrite

  # Load settings from a saved config file
  python main.py --cli --config my_settings.json
        """
    )

    # ── Paths ──
    p.add_argument("--source", "-s", metavar="FOLDER",
                   help="Source folder to process (required unless --config used)")
    p.add_argument("--output", "-o", metavar="FOLDER",
                   help="Output folder (required when --output-mode=separate)")
    p.add_argument("--output-mode", choices=OUTPUT_CHOICES, default="inplace",
                   help="inplace: modify files where they are | separate: write to output folder (default: inplace)")

    # ── Run behaviour ──
    p.add_argument("--dry-run", action="store_true",
                   help="Simulate everything — touch nothing")
    p.add_argument("--reprocess", action="store_true",
                   help="Force reprocess files already done in a previous run")
    p.add_argument("--backup", action="store_true",
                   help="Backup original files before writing (adds .bak extension)")
    p.add_argument("--no-verify", action="store_true",
                   help="Skip post-write EXIF verification (faster but less safe)")
    p.add_argument("--cleanup-progress", action="store_true",
                   help="Delete the progress tracking file after a successful run")

    # ── Field toggles ──
    fields_group = p.add_argument_group("Field toggles (default: all enabled except creation-date and google-url)")
    fields_group.add_argument("--no-date",        action="store_true", help="Skip writing photo taken date")
    fields_group.add_argument("--write-creation", action="store_true", help="Also write upload/creation date")
    fields_group.add_argument("--no-gps",         action="store_true", help="Skip writing GPS data")
    fields_group.add_argument("--no-description", action="store_true", help="Skip writing description")
    fields_group.add_argument("--no-title",       action="store_true", help="Skip writing title")
    fields_group.add_argument("--no-people",      action="store_true", help="Skip writing person tags")
    fields_group.add_argument("--write-url",      action="store_true", help="Write Google Photos URL to metadata")

    # ── Conflict policies ──
    conflict_group = p.add_argument_group("Conflict policies (what to do if field already exists in file)")
    for field in ["photo-date", "creation-date", "gps", "description", "title", "people", "google-url"]:
        conflict_group.add_argument(
            f"--conflict-{field}",
            choices=CONFLICT_CHOICES, default="skip",
            metavar="POLICY",
            help=f"skip|overwrite|prefer_newer for {field} (default: skip)"
        )

    # ── GPS zero policy ──
    p.add_argument("--gps-zero-policy", choices=GPS_ZERO_CHOICES, default="skip",
                   help="What to do when GPS is 0.0/missing: skip|overwrite_empty|warn|leave (default: skip)")

    # ── Timezone ──
    p.add_argument("--timezone", default="utc",
                   help="Timezone for date conversion: utc | local | Region/City e.g. Asia/Karachi (default: utc)")

    # ── Unmatched JSONs ──
    p.add_argument("--unmatched-policy", choices=UNMATCHED_CHOICES, default="keep",
                   help="What to do with JSONs that have no matching media: keep|move|delete (default: keep)")

    # ── Config file ──
    p.add_argument("--config", metavar="FILE",
                   help="Load settings from a JSON config file (overrides defaults, CLI args override config)")
    p.add_argument("--save-config", metavar="FILE",
                   help="Save current settings to a JSON config file and exit")

    # ── Log dir ──
    p.add_argument("--log-dir", metavar="FOLDER",
                   help="Where to write log files (default: same folder as this script)")

    # ── Version ──
    p.add_argument("--version", action="version", version="%(prog)s 1.0.0")

    return p


def args_to_runconfig(args: argparse.Namespace) -> RunConfig:
    """Convert parsed args to a RunConfig."""
    cfg = RunConfig()

    # Load from config file first if provided
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cfg = RunConfig.from_dict(data)
        else:
            print(f"[WARNING] Config file not found: {args.config}")

    # CLI args override config file
    if args.source:
        cfg.source_folder = args.source
    if args.output:
        cfg.output_folder = args.output

    cfg.output_mode       = args.output_mode
    cfg.dry_run           = args.dry_run or cfg.dry_run
    cfg.force_reprocess   = args.reprocess or cfg.force_reprocess
    cfg.cleanup_progress_file = args.cleanup_progress

    m = cfg.metadata
    m.backup_originals  = args.backup or m.backup_originals
    m.verify_after_write = not args.no_verify
    m.gps_zero_policy   = args.gps_zero_policy
    m.timezone          = args.timezone

    # Field enabled/disabled
    m.photo_taken_date.enabled  = not args.no_date
    m.creation_date.enabled     = args.write_creation
    m.gps.enabled               = not args.no_gps
    m.description.enabled       = not args.no_description
    m.title.enabled             = not args.no_title
    m.people.enabled            = not args.no_people
    m.google_url.enabled        = args.write_url

    # Conflict policies
    m.photo_taken_date.conflict_policy = args.conflict_photo_date
    m.creation_date.conflict_policy    = args.conflict_creation_date
    m.gps.conflict_policy              = args.conflict_gps
    m.description.conflict_policy      = args.conflict_description
    m.title.conflict_policy            = args.conflict_title
    m.people.conflict_policy           = args.conflict_people
    m.google_url.conflict_policy       = args.conflict_google_url

    cfg.unmatched_policy = args.unmatched_policy

    return cfg


def _make_progress_bar(total: int):
    if HAS_TQDM:
        return tqdm(total=total, unit="file", ncols=72, colour="green")
    return None


def run_cli(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # ── Check exiftool ──
    available, version = check_exiftool()
    if not available:
        print("\n❌ exiftool not found.")
        print("   Please download it from: https://exiftool.org")
        print("   Then add it to your system PATH and restart this tool.\n")
        sys.exit(1)
    print(f"✓ exiftool version {version} found.")

    cfg = args_to_runconfig(args)

    # ── Validate ──
    if not cfg.source_folder:
        print("\n❌ --source is required.\n")
        parser.print_help()
        sys.exit(1)

    source = Path(cfg.source_folder)
    if not source.exists() or not source.is_dir():
        print(f"\n❌ Source folder does not exist: {cfg.source_folder}\n")
        sys.exit(1)

    if cfg.output_mode == "separate" and not cfg.output_folder:
        print("\n❌ --output is required when --output-mode=separate\n")
        sys.exit(1)

    # ── Save config and exit ──
    if args.save_config:
        with open(args.save_config, 'w', encoding='utf-8') as f:
            json.dump(cfg.to_dict(), f, indent=2)
        print(f"✓ Config saved to: {args.save_config}")
        sys.exit(0)

    # ── Print run summary ──
    _print_run_summary(cfg)

    if cfg.dry_run:
        print("\n🔍 DRY RUN MODE — nothing will be written or deleted.\n")

    # ── Confirm (unless dry run) ──
    if not cfg.dry_run:
        try:
            confirm = input("Proceed? [Y/n]: ").strip().lower()
            if confirm not in ("", "y", "yes"):
                print("Aborted.")
                sys.exit(0)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(0)

    # ── Progress bar setup ──
    pbar = None
    _last_total = [0]

    def progress_callback(current: int, total: int, msg: str):
        nonlocal pbar
        if total > 0 and pbar is None and HAS_TQDM:
            pbar = tqdm(total=total, unit="file", ncols=72, colour="green")
            _last_total[0] = total
        if pbar:
            pbar.set_description(msg[:40])
            pbar.n = current
            pbar.refresh()

    def log_callback(msg: str):
        # In CLI mode, suppress debug lines from stdout (they go to log file)
        if "[DEBUG]" not in msg:
            if pbar:
                pbar.write(msg)
            else:
                print(msg)

    log_dir = Path(args.log_dir) if args.log_dir else Path(__file__).parent.parent

    # ── Run ──
    engine = Engine(
        config=cfg,
        log_dir=log_dir,
        progress_callback=progress_callback,
        log_callback=log_callback
    )

    try:
        result = engine.run()
    except KeyboardInterrupt:
        print("\n\nStopped by user. Progress has been saved — resume by running again.")
        sys.exit(0)
    finally:
        if pbar:
            pbar.close()

    if result.get("status") == "nothing_to_do":
        print("\n⚠  No supplemental-metadata.json files found in the source folder.")
    else:
        print(result.get("summary", ""))
        if result.get("log_path"):
            print(f"\n📄 Full log: {result['log_path']}")
        if result.get("failed_path"):
            print(f"⚠  Failed files: {result['failed_path']}")


def _print_run_summary(cfg: RunConfig):
    m = cfg.metadata
    enabled_fields = [
        name for name in ["photo_taken_date", "creation_date", "gps",
                           "description", "title", "people", "google_url"]
        if getattr(m, name).enabled
    ]
    print("\n┌─────────────────────────────────────────┐")
    print("│     METADATA RESTORE — RUN SETTINGS     │")
    print("├─────────────────────────────────────────┤")
    print(f"│  Source  : {str(cfg.source_folder)[:37]:<37} │")
    print(f"│  Mode    : {cfg.output_mode:<37} │")
    print(f"│  Dry run : {'YES' if cfg.dry_run else 'NO':<37} │")
    print(f"│  Fields  : {', '.join(enabled_fields)[:37]:<37} │")
    print(f"│  GPS 0.0 : {cfg.metadata.gps_zero_policy:<37} │")
    print(f"│  TZ      : {cfg.metadata.timezone:<37} │")
    print(f"│  Unmatched: {cfg.unmatched_policy:<36} │")
    print("└─────────────────────────────────────────┘")

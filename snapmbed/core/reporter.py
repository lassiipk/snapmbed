"""
SnapMbed — Reporter
Generates a detailed text summary report after processing.
"""

import os
import datetime


def generate_report(folder_path, stats, log_entries, opts):
    """
    Write a snapmbed_report.txt to folder_path.
    stats      : dict from the run (written, skipped, errors, etc.)
    log_entries: list of (status, message) tuples
    opts       : the options dict used for the run
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []

    lines.append("=" * 60)
    lines.append("  SnapMbed — Processing Report")
    lines.append(f"  Generated: {now}")
    lines.append("=" * 60)
    lines.append("")

    lines.append("FOLDER")
    lines.append(f"  {folder_path}")
    lines.append("")

    lines.append("OPTIONS USED")
    lines.append(f"  Force overwrite : {'Yes' if opts.get('force') else 'No'}")
    lines.append(f"  Embed GPS       : {'Yes' if opts.get('embed_gps') else 'No'}")
    lines.append(f"  Embed people    : {'Yes' if opts.get('embed_people') else 'No'}")
    lines.append(f"  Delete JSON     : {'Yes' if opts.get('delete_json') else 'No'}")
    lines.append(f"  Organise files  : {'Yes — ' + opts.get('org_structure', '') if opts.get('organise') else 'No'}")
    lines.append(f"  Rename files    : {'Yes' if opts.get('sanitise') else 'No'}")
    lines.append(f"  Timezone offset : UTC{opts.get('tz_offset', 0):+.1f}")
    lines.append(f"  Dry run         : {'Yes' if opts.get('dry_run') else 'No'}")
    lines.append("")

    lines.append("SUMMARY")
    lines.append(f"  Total scanned   : {stats.get('total', 0)}")
    lines.append(f"  Written         : {stats.get('written', 0)}")
    lines.append(f"  Skipped         : {stats.get('skipped', 0)}")
    lines.append(f"  No JSON sidecar : {stats.get('no_json', 0)}")
    lines.append(f"  Errors          : {stats.get('errors', 0)}")
    lines.append(f"  JSON deleted    : {stats.get('json_deleted', 0)}")
    lines.append(f"  Organised       : {stats.get('organised', 0)}")
    lines.append(f"  Renamed         : {stats.get('renamed', 0)}")
    lines.append("")

    # Group log entries by status
    errors   = [(s, m) for s, m in log_entries if s == "err"]
    no_jsons = [(s, m) for s, m in log_entries if s == "no_json"]

    if errors:
        lines.append(f"ERRORS ({len(errors)})")
        for _, msg in errors:
            lines.append(f"  ✗ {msg}")
        lines.append("")

    if no_jsons:
        lines.append(f"FILES WITHOUT JSON SIDECAR ({len(no_jsons)})")
        for _, msg in no_jsons:
            lines.append(f"  · {msg}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("  End of report")
    lines.append("=" * 60)

    report_text = "\n".join(lines)

    report_path = os.path.join(folder_path, "snapmbed_report.txt")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        return report_path
    except Exception as e:
        return None

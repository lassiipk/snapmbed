"""
SnapMbed — Main GUI
CustomTkinter dark-theme interface matching the HTML version.
"""

import os
import sys
import threading
import datetime
import tkinter as tk
from tkinter import filedialog, font as tkfont
import customtkinter as ctk

from gui.theme import COLORS as C, FONTS as F, PAD, GAP, RADIUS

# ── CustomTkinter global appearance ──────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ═══════════════════════════════════════════════════════════════
#  Reusable widget helpers
# ═══════════════════════════════════════════════════════════════

class Card(ctk.CTkFrame):
    """A surface card with a small uppercase title label."""
    def __init__(self, parent, title="", **kwargs):
        super().__init__(parent,
            fg_color=C["surface"],
            border_color=C["border"],
            border_width=1,
            corner_radius=RADIUS,
            **kwargs)
        if title:
            lbl = ctk.CTkLabel(self, text=title.upper(),
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                text_color=C["muted"])
            lbl.pack(anchor="w", padx=PAD, pady=(PAD, 0))

    def body(self):
        """Returns a padded inner frame for content."""
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=PAD, pady=(8, PAD))
        return f


class StatCard(ctk.CTkFrame):
    def __init__(self, parent, label, color, **kwargs):
        super().__init__(parent,
            fg_color=C["surface2"],
            border_color=C["border"],
            border_width=1,
            corner_radius=8,
            **kwargs)
        self._num_var = ctk.StringVar(value="0")
        ctk.CTkLabel(self, textvariable=self._num_var,
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=color).pack(pady=(10, 0))
        ctk.CTkLabel(self, text=label,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=C["muted"]).pack(pady=(0, 10))

    def set(self, val):
        self._num_var.set(str(val))


class SectionLabel(ctk.CTkLabel):
    def __init__(self, parent, text, **kwargs):
        super().__init__(parent, text=text,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=C["text"],
            **kwargs)


class MutedLabel(ctk.CTkLabel):
    def __init__(self, parent, text, **kwargs):
        super().__init__(parent, text=text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["muted"],
            **kwargs)


class PrimaryBtn(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        super().__init__(parent, text=text, command=command,
            fg_color=C["accent"],
            hover_color=C["accent2"],
            text_color="#ffffff",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=8,
            height=36,
            **kwargs)


class SecondaryBtn(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        super().__init__(parent, text=text, command=command,
            fg_color=C["surface2"],
            hover_color=C["border"],
            text_color=C["text"],
            border_color=C["border"],
            border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=8,
            height=32,
            **kwargs)


class ToggleRow(ctk.CTkFrame):
    """A label + description + toggle switch row."""
    def __init__(self, parent, label, desc="", default=True, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._var = ctk.BooleanVar(value=default)

        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text_frame, text=label,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=C["text"]).pack(anchor="w")
        if desc:
            ctk.CTkLabel(text_frame, text=desc,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=C["muted"],
                wraplength=520,
                justify="left").pack(anchor="w")

        self._switch = ctk.CTkSwitch(self, variable=self._var,
            text="",
            button_color=C["accent"],
            button_hover_color=C["accent2"],
            progress_color=C["accent"],
            width=40)
        self._switch.pack(side="right", padx=(8, 0))

    @property
    def value(self):
        return self._var.get()

    def set(self, val):
        self._var.set(val)

    def configure_state(self, state):
        self._switch.configure(state=state)


# ═══════════════════════════════════════════════════════════════
#  Main Application Window
# ═══════════════════════════════════════════════════════════════

class SnapMbedApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("SnapMbed — Google Takeout Metadata Embedder")
        self.geometry("920x860")
        self.minsize(800, 700)
        self.configure(fg_color=C["bg"])

        # State
        self._folder_path   = None
        self._all_files     = {}
        self._json_map      = {}
        self._media_files   = []
        self._raw_files     = []
        self._scan_stats    = {}
        self._processing    = False
        self._log_entries   = []   # (status, message) for report
        self._processed_set = set()

        self._build_ui()

    # ─────────────────────────────────────────────────────────
    #  UI Construction
    # ─────────────────────────────────────────────────────────

    def _build_ui(self):
        # Outer scroll container
        self._scroll = ctk.CTkScrollableFrame(self,
            fg_color=C["bg"],
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent"])
        self._scroll.pack(fill="both", expand=True, padx=0, pady=0)

        wrap = self._scroll
        wrap.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────
        hdr = ctk.CTkFrame(wrap, fg_color="transparent")
        hdr.pack(fill="x", padx=PAD, pady=(PAD, 0))

        logo = ctk.CTkFrame(hdr,
            fg_color=C["accent"],
            corner_radius=10,
            width=44, height=44)
        logo.pack(side="left", padx=(0, 12))
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="📸", font=ctk.CTkFont(size=20)).pack(expand=True)

        title_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        title_frame.pack(side="left")
        ctk.CTkLabel(title_frame, text="SnapMbed",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=C["accent2"]).pack(anchor="w")
        ctk.CTkLabel(title_frame,
            text="Google Takeout metadata embedder — 100% local, no internet required",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["muted"]).pack(anchor="w")

        # ── Step 1: Folder ───────────────────────────────────
        self._build_step1(wrap)

        # ── Skip warning (hidden initially) ──────────────────
        self._skip_warn = ctk.CTkFrame(wrap,
            fg_color=C["warn_bg"],
            border_color=C["warn_border"],
            border_width=1,
            corner_radius=RADIUS)
        # Not packed yet

        self._skip_warn_lbl = ctk.CTkLabel(self._skip_warn,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["yellow"],
            wraplength=820, justify="left")
        self._skip_warn_lbl.pack(padx=PAD, pady=10)

        # ── EXIF Inspector (hidden initially) ────────────────
        self._build_inspector(wrap)

        # ── Step 2: Options ──────────────────────────────────
        self._build_step2(wrap)

        # ── Step 3: Output mode ──────────────────────────────
        self._build_step3(wrap)

        # ── Step 4: Organise ─────────────────────────────────
        self._build_step4(wrap)

        # ── Step 5: Advanced ─────────────────────────────────
        self._build_step5(wrap)

        # ── Step 6: Run ──────────────────────────────────────
        self._build_step6(wrap)

        # ── Progress ─────────────────────────────────────────
        self._build_progress(wrap)

        # ── Stats bar ────────────────────────────────────────
        self._build_stats(wrap)

        # ── Done banner (hidden) ─────────────────────────────
        self._done_banner = ctk.CTkFrame(wrap,
            fg_color=C["ok_bg"],
            border_color=C["ok_border"],
            border_width=1,
            corner_radius=RADIUS)
        self._done_lbl = ctk.CTkLabel(self._done_banner,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=C["green"])
        self._done_lbl.pack(padx=PAD, pady=12)

        # ── Log ──────────────────────────────────────────────
        self._build_log(wrap)

    # ── Step 1 ───────────────────────────────────────────────

    def _build_step1(self, parent):
        card = Card(parent, "Step 1 — Select your Takeout folder")
        card.pack(fill="x", padx=PAD, pady=(PAD, 0))
        body = card.body()

        # Browse button row
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x")

        self._folder_lbl = ctk.CTkLabel(btn_row,
            text="No folder selected",
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color=C["muted"])
        self._folder_lbl.pack(side="left", fill="x", expand=True)

        PrimaryBtn(btn_row, "  🗂  Browse Folder",
            command=self._browse_folder).pack(side="right")

        # Folder info bar (hidden initially)
        self._folder_info = ctk.CTkFrame(body,
            fg_color=C["surface2"],
            border_color=C["border"],
            border_width=1,
            corner_radius=8)
        self._folder_info_lbl = ctk.CTkLabel(self._folder_info,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["muted"])
        self._folder_info_lbl.pack(padx=14, pady=8)

    # ── EXIF Inspector ────────────────────────────────────────

    def _build_inspector(self, parent):
        self._inspector_card = Card(parent,
            "EXIF Inspector — verify metadata before & after processing")
        # Not packed yet

        body = self._inspector_card.body()

        inp_row = ctk.CTkFrame(body, fg_color="transparent")
        inp_row.pack(fill="x")
        self._inspector_entry = ctk.CTkEntry(inp_row,
            placeholder_text="Paste a relative image path, e.g.  2024/IMG_001.jpg",
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color=C["surface2"],
            border_color=C["border"],
            text_color=C["text"],
            height=34)
        self._inspector_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        SecondaryBtn(inp_row, "🔍  Inspect",
            command=self._run_inspector).pack(side="right")

        self._inspector_result = ctk.CTkTextbox(body,
            height=160,
            fg_color="#0a0a0c",
            border_color=C["border"],
            border_width=1,
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color=C["muted"],
            state="disabled",
            corner_radius=8)
        self._inspector_result.pack(fill="x", pady=(8, 0))

        MutedLabel(body,
            text="Shows current EXIF in the file vs what the JSON sidecar contains. "
                 "Run again after processing to confirm the write succeeded."
        ).pack(anchor="w", pady=(4, 0))

    # ── Step 2 ───────────────────────────────────────────────

    def _build_step2(self, parent):
        card = Card(parent, "Step 2 — Metadata Options")
        card.pack(fill="x", padx=PAD, pady=(PAD, 0))
        body = card.body()

        self._opt_force = ToggleRow(body,
            "Force overwrite existing EXIF fields",
            desc="OFF (default) — only fills missing fields.  "
                 "ON — overwrites everything from JSON, even existing dates/GPS. "
                 "Use if your camera clock was wrong.",
            default=False)
        self._opt_force.pack(fill="x", pady=(0, 6))
        _divider(body)

        self._opt_gps = ToggleRow(body,
            "Embed GPS coordinates",
            desc="Only embeds if lat/lng are non-zero in the JSON.",
            default=True)
        self._opt_gps.pack(fill="x", pady=6)
        _divider(body)

        self._opt_people = ToggleRow(body,
            "Embed people names",
            desc="Written to EXIF Artist / XPComment fields.",
            default=True)
        self._opt_people.pack(fill="x", pady=(6, 0))

    # ── Step 3 ───────────────────────────────────────────────

    def _build_step3(self, parent):
        card = Card(parent, "Step 3 — Output & Cleanup")
        card.pack(fill="x", padx=PAD, pady=(PAD, 0))
        body = card.body()

        self._opt_delete_json = ToggleRow(body,
            "Delete JSON sidecar files after processing",
            desc="Removes the .supplemental-metadata.json files once metadata is embedded. "
                 "Keeps your folder clean. Skipped files / errors keep their JSON.",
            default=True)
        self._opt_delete_json.pack(fill="x", pady=(0, 6))
        _divider(body)

        self._opt_dry_run = ToggleRow(body,
            "Dry run — simulate only, write nothing",
            desc="Processes everything but makes zero changes to disk. "
                 "Shows exactly what would happen before you commit.",
            default=False)
        self._opt_dry_run.pack(fill="x", pady=(6, 0))

    # ── Step 4 ───────────────────────────────────────────────

    def _build_step4(self, parent):
        card = Card(parent, "Step 4 — Organise by Date  (optional)")
        card.pack(fill="x", padx=PAD, pady=(PAD, 0))
        body = card.body()

        self._opt_organise = ToggleRow(body,
            "Organise files into dated folders",
            desc="Moves processed images into a folder structure based on photo date taken.",
            default=False)
        self._opt_organise.pack(fill="x")
        self._opt_organise._switch.configure(command=self._toggle_organise)

        # Sub-options (hidden until toggle is ON)
        self._org_sub = ctk.CTkFrame(body, fg_color="transparent")

        MutedLabel(self._org_sub, text="Folder structure:").pack(anchor="w", pady=(8, 4))

        self._org_var = ctk.StringVar(value="year-month")
        seg = ctk.CTkSegmentedButton(self._org_sub,
            values=["Year only", "Year / Month", "Year / Month / Day"],
            variable=self._org_var,
            command=self._update_org_preview,
            fg_color=C["surface2"],
            selected_color=C["accent"],
            selected_hover_color=C["accent2"],
            unselected_color=C["surface2"],
            unselected_hover_color=C["border"],
            text_color=C["text"],
            font=ctk.CTkFont(family="Segoe UI", size=11))
        seg.pack(anchor="w")
        # Map display values to internal values
        self._org_display_map = {
            "Year only":           "year",
            "Year / Month":        "year-month",
            "Year / Month / Day":  "year-month-day",
        }

        self._org_preview = ctk.CTkTextbox(self._org_sub,
            height=80,
            fg_color="#0a0a0c",
            border_color=C["border"],
            border_width=1,
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=C["blue"],
            state="disabled",
            corner_radius=8)
        self._org_preview.pack(fill="x", pady=(8, 0))
        self._update_org_preview()

    def _toggle_organise(self):
        if self._opt_organise.value:
            self._org_sub.pack(fill="x", pady=(4, 0))
        else:
            self._org_sub.pack_forget()

    def _update_org_preview(self, *_):
        mode = self._org_display_map.get(self._org_var.get(), "year-month")
        if mode == "year":
            preview = "📁 2024/\n  └─ IMG_001.jpg\n  └─ IMG_002.jpg\n📁 2023/\n  └─ Photo_005.jpg"
        elif mode == "year-month":
            preview = "📁 2024/\n  📁 03 - March/\n    └─ IMG_001.jpg\n    └─ IMG_002.jpg\n  📁 11 - November/\n    └─ Photo_005.jpg"
        else:
            preview = "📁 2024/\n  📁 03 - March/\n    📁 15/\n      └─ IMG_001.jpg\n    📁 16/\n      └─ IMG_002.jpg"
        self._org_preview.configure(state="normal")
        self._org_preview.delete("0.0", "end")
        self._org_preview.insert("0.0", preview)
        self._org_preview.configure(state="disabled")

    # ── Step 5: Advanced ─────────────────────────────────────

    def _build_step5(self, parent):
        card = Card(parent, "Step 5 — Advanced Options  (optional)")
        card.pack(fill="x", padx=PAD, pady=(PAD, 0))
        body = card.body()

        self._opt_sanitise = ToggleRow(body,
            "Sanitise filenames — rename cryptic files by date",
            desc="Renames files like AF1Qip_abc123.jpg → 2024-03-15_001.jpg. "
                 "Only renames if the filename doesn't already contain a date.",
            default=False)
        self._opt_sanitise.pack(fill="x", pady=(0, 6))
        _divider(body)

        self._opt_resume = ToggleRow(body,
            "Resume interrupted runs",
            desc="Remembers which files were already processed. "
                 "If the run is cancelled, the next run picks up where it left off.",
            default=True)
        self._opt_resume.pack(fill="x", pady=(6, 6))
        _divider(body)

        # Timezone row
        tz_row = ctk.CTkFrame(body, fg_color="transparent")
        tz_row.pack(fill="x", pady=(6, 0))

        tz_text = ctk.CTkFrame(tz_row, fg_color="transparent")
        tz_text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(tz_text, text="Timezone offset (hours from UTC)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=C["text"]).pack(anchor="w")
        ctk.CTkLabel(tz_text,
            text="Google timestamps are UTC. Set your local offset so dates are written correctly.\n"
                 "Pakistan = +5.0 | India = +5.5 | UK = 0 | US Eastern = -5",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=C["muted"],
            justify="left").pack(anchor="w")

        self._tz_var = ctk.StringVar(value="+5.0")
        tz_entry = ctk.CTkEntry(tz_row,
            textvariable=self._tz_var,
            width=70,
            font=ctk.CTkFont(family="Courier New", size=12),
            fg_color=C["surface2"],
            border_color=C["border"],
            text_color=C["text"],
            justify="center",
            height=32)
        tz_entry.pack(side="right", padx=(8, 0))

    # ── Step 6: Run ──────────────────────────────────────────

    def _build_step6(self, parent):
        card = Card(parent, "Step 6 — Process")
        card.pack(fill="x", padx=PAD, pady=(PAD, 0))
        body = card.body()

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(anchor="w")

        self._run_btn = PrimaryBtn(btn_row, "▶   Start Processing",
            command=self._start_processing)
        self._run_btn.pack(side="left", padx=(0, 8))
        self._run_btn.configure(state="disabled")

        self._dry_run_btn = SecondaryBtn(btn_row, "🔬  Dry Run",
            command=self._start_dry_run)
        self._dry_run_btn.pack(side="left", padx=(0, 8))
        self._dry_run_btn.configure(state="disabled")

        self._clear_btn = SecondaryBtn(btn_row, "✕  Clear",
            command=self._clear)
        self._clear_btn.pack(side="left")
        self._clear_btn.configure(state="disabled")

    # ── Progress ─────────────────────────────────────────────

    def _build_progress(self, parent):
        self._progress_frame = ctk.CTkFrame(parent,
            fg_color="transparent")

        ctk.CTkLabel(self._progress_frame,
            text="PROCESSING…",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=C["muted"]).pack(anchor="w", padx=PAD, pady=(PAD, 4))

        self._progress_bar = ctk.CTkProgressBar(self._progress_frame,
            fg_color=C["surface2"],
            progress_color=C["accent"],
            height=6,
            corner_radius=99)
        self._progress_bar.pack(fill="x", padx=PAD)
        self._progress_bar.set(0)

        self._progress_lbl = ctk.CTkLabel(self._progress_frame,
            text="0 / 0",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["muted"])
        self._progress_lbl.pack(anchor="w", padx=PAD, pady=(4, PAD))

    # ── Stats bar ────────────────────────────────────────────

    def _build_stats(self, parent):
        self._stats_frame = ctk.CTkFrame(parent, fg_color="transparent")

        row = ctk.CTkFrame(self._stats_frame, fg_color="transparent")
        row.pack(fill="x", padx=PAD, pady=(0, PAD))
        row.grid_columnconfigure((0,1,2,3,4), weight=1)

        self._s_written  = StatCard(row, "Metadata written",  C["green"])
        self._s_skipped  = StatCard(row, "Already complete",  C["yellow"])
        self._s_nojson   = StatCard(row, "No JSON sidecar",   C["blue"])
        self._s_errors   = StatCard(row, "Errors",            C["red"])
        self._s_total    = StatCard(row, "Total scanned",     C["accent2"])

        for i, s in enumerate([self._s_written, self._s_skipped,
                                self._s_nojson, self._s_errors, self._s_total]):
            s.grid(row=0, column=i, padx=4, sticky="ew")

    # ── Log ──────────────────────────────────────────────────

    def _build_log(self, parent):
        self._log_frame = ctk.CTkFrame(parent, fg_color="transparent")

        hdr = ctk.CTkFrame(self._log_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=PAD, pady=(0, 6))
        ctk.CTkLabel(hdr, text="ACTIVITY LOG",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=C["muted"]).pack(side="left")
        ctk.CTkLabel(hdr, text="LIVE",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            fg_color=C["accent"],
            text_color="#fff",
            corner_radius=4,
            padx=6, pady=1).pack(side="left", padx=6)

        self._log_box = ctk.CTkTextbox(self._log_frame,
            height=280,
            fg_color="#0a0a0c",
            border_color=C["border"],
            border_width=1,
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color=C["muted"],
            corner_radius=8,
            state="disabled")
        self._log_box.pack(fill="x", padx=PAD)

        # Configure color tags
        self._log_box._textbox.tag_configure("ok",   foreground=C["green"])
        self._log_box._textbox.tag_configure("skip", foreground=C["yellow"])
        self._log_box._textbox.tag_configure("err",  foreground=C["red"])
        self._log_box._textbox.tag_configure("info", foreground=C["blue"])
        self._log_box._textbox.tag_configure("dim",  foreground=C["muted"])
        self._log_box._textbox.tag_configure("dry",  foreground=C["accent2"])

        btn_row = ctk.CTkFrame(self._log_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=PAD, pady=(8, PAD))
        SecondaryBtn(btn_row, "💾  Save log as .txt",
            command=self._save_log).pack(side="left", padx=(0, 8))
        SecondaryBtn(btn_row, "📄  Open Report",
            command=self._open_report).pack(side="left")

        self._report_path = None

    # ─────────────────────────────────────────────────────────
    #  Actions
    # ─────────────────────────────────────────────────────────

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select your Google Takeout folder")
        if not path:
            return
        self._folder_path = path
        self._folder_lbl.configure(
            text=path if len(path) < 70 else "…" + path[-67:],
            text_color=C["text"])
        self._scan_folder()

    def _scan_folder(self):
        self._log_clear()
        self._log("Scanning folder…", "info")
        self.update_idletasks()

        from core.scanner import scan_folder
        from core.cleaner import load_state

        af, jm, mf, rf, stats = scan_folder(self._folder_path)
        self._all_files   = af
        self._json_map    = jm
        self._media_files = mf
        self._raw_files   = rf
        self._scan_stats  = stats

        if self._opt_resume.value:
            self._processed_set = load_state(self._folder_path)
        else:
            self._processed_set = set()

        # Folder info bar
        matched = stats["matched_json"]
        total   = stats["total_media"]
        no_json = stats["no_json"]
        info_txt = (f"  {total} media files  ·  {matched} JSON sidecars matched  ·  "
                    f"{no_json} without JSON")
        if rf:
            info_txt += f"  ·  {len(rf)} RAW files (skipped safely)"
        self._folder_info_lbl.configure(text=info_txt, text_color=C["muted"])
        self._folder_info.pack(fill="x", pady=(8, 0))

        # Skip warning
        warned = stats.get("warned", {})
        if warned:
            parts = []
            labels = {".heic":"HEIC", ".png":"PNG", ".webp":"WebP",
                      ".mp4":"MP4", ".mov":"MOV", ".tiff":"TIFF",
                      ".jfif":"JFIF", ".gif":"GIF", ".bmp":"BMP"}
            for ext, count in warned.items():
                parts.append(f"{count} {labels.get(ext, ext.upper())}")
            warn_txt = (f"⚠  Non-processable files with JSON sidecars: {', '.join(parts)}\n"
                        f"These formats cannot have EXIF embedded and will be skipped.")
            self._skip_warn_lbl.configure(text=warn_txt)
            self._skip_warn.pack(fill="x", padx=PAD, pady=(PAD, 0))
        else:
            self._skip_warn.pack_forget()

        # Inspector card
        self._inspector_card.pack(fill="x", padx=PAD, pady=(PAD, 0))
        # Set placeholder to an actual example path
        if mf:
            self._inspector_entry.configure(
                placeholder_text=mf[0])

        # Enable buttons
        if total > 0:
            self._run_btn.configure(state="normal")
            self._dry_run_btn.configure(state="normal")
        self._clear_btn.configure(state="normal")

        self._log(
            f"Scan complete — {total} media files, {matched} matched to JSON sidecars.",
            "info")
        self._log("", "dim")

    def _run_inspector(self):
        path = self._inspector_entry.get().strip()
        if not path:
            self._inspector_write("Enter a relative image path first.", "err")
            return

        # Normalise separators
        path_norm = path.replace("\\", "/")
        abs_path = None
        for rel, abs_p in self._all_files.items():
            if rel.replace("\\", "/") == path_norm:
                abs_path = abs_p
                rel_key  = rel
                break

        if not abs_path:
            self._inspector_write(f"File not found in loaded folder:\n  {path}", "err")
            return

        lines = []
        ext = os.path.splitext(abs_path.lower())[1]

        # Read EXIF
        if ext in {".jpg", ".jpeg", ".jfif", ".jpe", ".tiff", ".tif", ".webp", ".heic", ".heif"}:
            try:
                import piexif
                from PIL import Image
                if ext in {".heic", ".heif"}:
                    try:
                        import pillow_heif
                        pillow_heif.register_heif_opener()
                    except ImportError:
                        pass
                img = Image.open(abs_path)
                exif_bytes = img.info.get("exif", b"")
                exif_dict  = piexif.load(exif_bytes) if exif_bytes else {}
                img.close()

                ifd0 = exif_dict.get("0th", {})
                exif = exif_dict.get("Exif", {})
                gps  = exif_dict.get("GPS", {})

                def _val(d, tag, fallback="(not set)"):
                    v = d.get(tag)
                    if v is None: return fallback
                    if isinstance(v, bytes):
                        try: return v.decode("utf-8").strip("\x00")
                        except: return repr(v)
                    return str(v)

                import piexif
                lines.append(f"── EXIF in file ──────────────────────────")
                dto = _val(exif, piexif.ExifIFD.DateTimeOriginal)
                lines.append(f"DateTimeOriginal   {dto}")
                lines.append(f"ImageDescription   {_val(ifd0, piexif.ImageIFD.ImageDescription)}")
                lines.append(f"Artist             {_val(ifd0, piexif.ImageIFD.Artist)}")
                glat = gps.get(piexif.GPSIFD.GPSLatitude)
                lines.append(f"GPS                {'set' if glat else '(not set)'}")
            except Exception as e:
                lines.append(f"Could not read EXIF: {e}")
        else:
            lines.append("(EXIF inspection not supported for this format)")

        # Read JSON sidecar
        json_rel = self._json_map.get(rel_key)
        if json_rel:
            json_abs = os.path.join(self._folder_path, json_rel)
            try:
                import json as _json
                with open(json_abs, "r", encoding="utf-8") as f:
                    meta = _json.load(f)
                lines.append("")
                lines.append("── JSON sidecar ──────────────────────────")
                pt = meta.get("photoTakenTime", {})
                lines.append(f"photoTakenTime     {pt.get('formatted', '(none)')}")
                geo = meta.get("geoData", {})
                lat, lng = geo.get("latitude", 0), geo.get("longitude", 0)
                if lat != 0 or lng != 0:
                    lines.append(f"geoData            {lat:.6f}, {lng:.6f}")
                else:
                    lines.append("geoData            (no GPS)")
                desc = meta.get("description", "").strip()
                lines.append(f"description        {desc if desc else '(empty)'}")
                people = meta.get("people", [])
                if people:
                    lines.append(f"people             {', '.join(p.get('name','') for p in people)}")
            except Exception as e:
                lines.append(f"Could not read JSON: {e}")
        else:
            lines.append("")
            lines.append("No JSON sidecar matched for this file.")

        self._inspector_write("\n".join(lines), "dim")

    def _inspector_write(self, text, tag="dim"):
        self._inspector_result.configure(state="normal")
        self._inspector_result.delete("0.0", "end")
        self._inspector_result.insert("0.0", text)
        self._inspector_result.configure(state="disabled")

    def _start_processing(self):
        self._run_with_opts(dry_run=False)

    def _start_dry_run(self):
        self._run_with_opts(dry_run=True)

    def _run_with_opts(self, dry_run=False):
        if self._processing:
            return
        if not self._folder_path or not self._media_files:
            return

        try:
            tz = float(self._tz_var.get())
        except ValueError:
            tz = 0.0

        org_display = self._org_var.get()
        org_structure = {
            "Year only":           "year",
            "Year / Month":        "year-month",
            "Year / Month / Day":  "year-month-day",
        }.get(org_display, "year-month")

        opts = {
            "force":        self._opt_force.value,
            "embed_gps":    self._opt_gps.value,
            "embed_people": self._opt_people.value,
            "delete_json":  self._opt_delete_json.value and not dry_run,
            "dry_run":      dry_run,
            "organise":     self._opt_organise.value,
            "org_structure":org_structure,
            "sanitise":     self._opt_sanitise.value,
            "resume":       self._opt_resume.value,
            "tz_offset":    tz,
        }

        self._processing = True
        self._run_btn.configure(state="disabled")
        self._dry_run_btn.configure(state="disabled")
        self._clear_btn.configure(state="disabled")
        self._done_banner.pack_forget()
        self._progress_frame.pack(fill="x", padx=PAD, pady=(PAD, 0))
        self._stats_frame.pack(fill="x", pady=(PAD, 0))
        self._log_frame.pack(fill="x", pady=(PAD, 0))
        self._log_clear()

        mode_label = "DRY RUN" if dry_run else "Processing"
        self._log(f"[SnapMbed] {mode_label} — {len(self._media_files)} media files to scan", "info")

        thread = threading.Thread(
            target=self._process_thread,
            args=(opts,),
            daemon=True)
        thread.start()

    def _process_thread(self, opts):
        from core.embedder  import process_file
        from core.organiser import organised_path, sanitise_filename, move_file, rename_file
        from core.cleaner   import delete_sidecar, save_state, clear_state
        from core.reporter  import generate_report

        total    = len(self._media_files)
        written  = 0
        skipped  = 0
        no_json  = 0
        errors   = 0
        json_del = 0
        organised= 0
        renamed  = 0
        log_entries = []
        sanitise_counter = {}  # per-date counter for filenames

        processed_set = self._processed_set.copy()

        for i, rel_path in enumerate(self._media_files):
            abs_path = os.path.join(self._folder_path, rel_path)

            # Update progress
            pct = (i + 1) / total
            fname = os.path.basename(rel_path)
            self.after(0, self._update_progress, pct, i + 1, total, fname)

            # Resume check
            if opts["resume"] and rel_path in processed_set:
                skipped += 1
                self.after(0, self._log, f"  [skip] {rel_path} — already processed (resume)", "skip")
                self.after(0, self._update_stats, written, skipped, no_json, errors, total)
                continue

            # JSON sidecar
            json_rel = self._json_map.get(rel_path)
            if not json_rel:
                no_json += 1
                msg = f"  [no json] {rel_path}"
                log_entries.append(("no_json", rel_path))
                self.after(0, self._log, msg, "dim")
                self.after(0, self._update_stats, written, skipped, no_json, errors, total)
                continue

            json_abs = os.path.join(self._folder_path, json_rel)

            # Embed
            result = process_file(abs_path, json_abs, opts, self._folder_path)

            current_abs = abs_path  # track if file moves

            if result["status"] in ("ok", "dry"):
                written += 1
                ts = result.get("ts_used")
                tag = "dry" if result["status"] == "dry" else "ok"
                label = "[dry run]" if result["status"] == "dry" else "[✓ written]"

                log_line = f"  {label} {rel_path}"

                # Sanitise filename
                if opts["sanitise"] and not opts["dry_run"]:
                    date_key = ts[:8] if ts else "undated"
                    sanitise_counter[date_key] = sanitise_counter.get(date_key, 0) + 1
                    new_name = sanitise_filename(
                        os.path.basename(rel_path), ts,
                        sanitise_counter[date_key], opts["tz_offset"])
                    if new_name != os.path.basename(rel_path):
                        new_abs = rename_file(current_abs, new_name)
                        current_abs = new_abs
                        renamed += 1
                        log_line += f"  →  {new_name}"

                # Organise
                if opts["organise"] and ts:
                    new_rel = organised_path(ts, rel_path, opts["org_structure"], opts["tz_offset"])
                    dest_abs = os.path.join(self._folder_path, new_rel)
                    if not opts["dry_run"] and dest_abs != current_abs:
                        move_file(current_abs, dest_abs)
                        organised += 1
                        log_line += f"  →  {new_rel}"

                self.after(0, self._log, log_line, tag)

                # Delete JSON sidecar
                if opts["delete_json"] and os.path.exists(json_abs):
                    if delete_sidecar(json_abs, opts["dry_run"]):
                        json_del += 1

                # Mark as processed
                processed_set.add(rel_path)
                log_entries.append(("ok", rel_path))

            elif result["status"] == "skip":
                skipped += 1
                self.after(0, self._log, f"  [skip] {rel_path} — {result['msg']}", "skip")
                log_entries.append(("skip", rel_path))

            else:
                errors += 1
                msg = f"  [ERR] {rel_path} — {result['msg']}"
                self.after(0, self._log, msg, "err")
                log_entries.append(("err", msg))

            self.after(0, self._update_stats, written, skipped, no_json, errors, total)

        # Save state
        if opts["resume"] and not opts["dry_run"]:
            save_state(self._folder_path, processed_set)

        # Generate report
        run_stats = {
            "total": total, "written": written, "skipped": skipped,
            "no_json": no_json, "errors": errors,
            "json_deleted": json_del, "organised": organised, "renamed": renamed,
        }

        report_path = None
        if not opts["dry_run"]:
            report_path = generate_report(
                self._folder_path, run_stats, log_entries, opts)

        self.after(0, self._processing_done,
                   written, skipped, no_json, errors, json_del,
                   organised, renamed, opts["dry_run"], report_path)

    # ─────────────────────────────────────────────────────────
    #  UI update helpers (called from thread via .after())
    # ─────────────────────────────────────────────────────────

    def _update_progress(self, pct, current, total, fname):
        self._progress_bar.set(pct)
        self._progress_lbl.configure(
            text=f"{current} / {total} — {fname}")

    def _update_stats(self, written, skipped, no_json, errors, total):
        self._s_written.set(written)
        self._s_skipped.set(skipped)
        self._s_nojson.set(no_json)
        self._s_errors.set(errors)
        self._s_total.set(total)

    def _processing_done(self, written, skipped, no_json, errors,
                         json_del, organised, renamed, dry_run, report_path):
        self._processing = False
        self._report_path = report_path
        self._progress_bar.set(1.0)
        self._progress_lbl.configure(text="Done!")

        mode = "Dry run complete" if dry_run else "Done!"
        parts = [
            f"{written} {'would be ' if dry_run else ''}written",
            f"{skipped} skipped",
            f"{no_json} no JSON",
            f"{errors} errors",
        ]
        if json_del:   parts.append(f"{json_del} JSON deleted")
        if organised:  parts.append(f"{organised} organised")
        if renamed:    parts.append(f"{renamed} renamed")

        self._done_lbl.configure(
            text=f"✅  {mode}   {'  ·  '.join(parts)}")
        self._done_banner.pack(fill="x", padx=PAD, pady=(PAD, 0))

        self._log("", "dim")
        self._log(f"[SnapMbed] Finished. " + "  ".join(parts), "info")
        if report_path:
            self._log(f"[SnapMbed] Report saved → {report_path}", "info")

        self._run_btn.configure(state="normal")
        self._dry_run_btn.configure(state="normal")
        self._clear_btn.configure(state="normal")

    def _log(self, msg, tag="dim"):
        self._log_box.configure(state="normal")
        self._log_box._textbox.insert("end", msg + "\n", tag)
        self._log_box._textbox.see("end")
        self._log_box.configure(state="disabled")

    def _log_clear(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("0.0", "end")
        self._log_box.configure(state="disabled")

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile="snapmbed_log.txt",
            title="Save log")
        if not path:
            return
        self._log_box.configure(state="normal")
        text = self._log_box.get("0.0", "end")
        self._log_box.configure(state="disabled")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _open_report(self):
        if self._report_path and os.path.exists(self._report_path):
            os.startfile(self._report_path)
        else:
            self._log("No report available yet — run processing first.", "skip")

    def _clear(self):
        self._folder_path   = None
        self._all_files     = {}
        self._json_map      = {}
        self._media_files   = []
        self._raw_files     = []
        self._scan_stats    = {}
        self._processed_set = set()
        self._report_path   = None

        self._folder_lbl.configure(text="No folder selected", text_color=C["muted"])
        self._folder_info.pack_forget()
        self._skip_warn.pack_forget()
        self._inspector_card.pack_forget()
        self._progress_frame.pack_forget()
        self._stats_frame.pack_forget()
        self._log_frame.pack_forget()
        self._done_banner.pack_forget()
        self._log_clear()

        self._progress_bar.set(0)
        self._progress_lbl.configure(text="0 / 0")
        for s in [self._s_written, self._s_skipped,
                  self._s_nojson, self._s_errors, self._s_total]:
            s.set(0)

        self._run_btn.configure(state="disabled")
        self._dry_run_btn.configure(state="disabled")
        self._clear_btn.configure(state="disabled")


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def _divider(parent):
    ctk.CTkFrame(parent,
        height=1,
        fg_color=C["border"],
        corner_radius=0).pack(fill="x", pady=2)

"""
SnapMbed — Main GUI
CustomTkinter dark-theme interface matching the HTML version.

Fix: All frames are packed at build time and hidden with pack_forget().
     Never pack-later into CTkScrollableFrame — it doesn't reflow reliably.
"""

import os
import sys
import threading
import datetime
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

from gui.theme import COLORS as C, PAD, RADIUS

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ═══════════════════════════════════════════════════════════════
#  Reusable widget helpers
# ═══════════════════════════════════════════════════════════════

class Card(ctk.CTkFrame):
    def __init__(self, parent, title="", **kwargs):
        super().__init__(parent,
            fg_color=C["surface"],
            border_color=C["border"],
            border_width=1,
            corner_radius=RADIUS,
            **kwargs)
        if title:
            ctk.CTkLabel(self, text=title.upper(),
                font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                text_color=C["muted"]).pack(anchor="w", padx=PAD, pady=(PAD, 0))

    def body(self):
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
        self._var = ctk.StringVar(value="0")
        ctk.CTkLabel(self, textvariable=self._var,
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=color).pack(pady=(10, 0))
        ctk.CTkLabel(self, text=label,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=C["muted"]).pack(pady=(0, 10))

    def set(self, val):
        self._var.set(str(val))


class ToggleRow(ctk.CTkFrame):
    def __init__(self, parent, label, desc="", default=True, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._var = ctk.BooleanVar(value=default)

        txt = ctk.CTkFrame(self, fg_color="transparent")
        txt.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(txt, text=label,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=C["text"]).pack(anchor="w")
        if desc:
            ctk.CTkLabel(txt, text=desc,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=C["muted"],
                wraplength=500, justify="left").pack(anchor="w")

        self._switch = ctk.CTkSwitch(self, variable=self._var, text="",
            button_color=C["accent"],
            button_hover_color=C["accent2"],
            progress_color=C["accent"],
            width=40)
        self._switch.pack(side="right", padx=(8, 0))

    @property
    def value(self):
        return self._var.get()


class PrimaryBtn(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        super().__init__(parent, text=text, command=command,
            fg_color=C["accent"], hover_color=C["accent2"],
            text_color="#fff",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            corner_radius=8, height=36, **kwargs)


class SecBtn(ctk.CTkButton):
    def __init__(self, parent, text, command=None, **kwargs):
        super().__init__(parent, text=text, command=command,
            fg_color=C["surface2"], hover_color=C["border"],
            text_color=C["text"],
            border_color=C["border"], border_width=1,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            corner_radius=8, height=32, **kwargs)


def _div(parent):
    ctk.CTkFrame(parent, height=1, fg_color=C["border"],
        corner_radius=0).pack(fill="x", pady=2)


# ═══════════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════════

class SnapMbedApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SnapMbed — Google Takeout Metadata Embedder")
        self.geometry("940x900")
        self.minsize(820, 700)
        self.configure(fg_color=C["bg"])

        self._folder_path   = None
        self._all_files     = {}
        self._json_map      = {}
        self._media_files   = []
        self._raw_files     = []
        self._processing    = False
        self._processed_set = set()
        self._report_path   = None

        self._build_ui()

    # ─────────────────────────────────────────────────────────
    #  Build UI  (everything packed immediately; hidden with pack_forget)
    # ─────────────────────────────────────────────────────────

    def _build_ui(self):
        self._scroll = ctk.CTkScrollableFrame(self,
            fg_color=C["bg"],
            scrollbar_button_color=C["border"],
            scrollbar_button_hover_color=C["accent"])
        self._scroll.pack(fill="both", expand=True)
        w = self._scroll   # alias

        # ── Header ──────────────────────────────────────────
        hdr = ctk.CTkFrame(w, fg_color="transparent")
        hdr.pack(fill="x", padx=PAD, pady=(PAD, 0))

        logo = ctk.CTkFrame(hdr, fg_color=C["accent"],
            corner_radius=10, width=44, height=44)
        logo.pack(side="left", padx=(0, 12))
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="📸",
            font=ctk.CTkFont(size=20)).pack(expand=True)

        tf = ctk.CTkFrame(hdr, fg_color="transparent")
        tf.pack(side="left")
        ctk.CTkLabel(tf, text="SnapMbed",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=C["accent2"]).pack(anchor="w")
        ctk.CTkLabel(tf,
            text="Google Takeout metadata embedder — 100% local, no internet required",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["muted"]).pack(anchor="w")

        # ── Step 1: Folder ───────────────────────────────────
        c1 = Card(w, "Step 1 — Select your Takeout folder")
        c1.pack(fill="x", padx=PAD, pady=(PAD, 0))
        b1 = c1.body()

        br = ctk.CTkFrame(b1, fg_color="transparent")
        br.pack(fill="x")
        self._folder_lbl = ctk.CTkLabel(br,
            text="No folder selected",
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color=C["muted"])
        self._folder_lbl.pack(side="left", fill="x", expand=True)
        PrimaryBtn(br, "  🗂  Browse Folder",
            command=self._browse_folder).pack(side="right")

        # Folder info bar — always in layout, hidden until scan
        self._folder_info = ctk.CTkFrame(b1,
            fg_color=C["surface2"], border_color=C["border"],
            border_width=1, corner_radius=8)
        self._folder_info_lbl = ctk.CTkLabel(self._folder_info,
            text="", font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["muted"])
        self._folder_info_lbl.pack(padx=14, pady=8)
        self._folder_info.pack_forget()

        # ── Skip warning ─────────────────────────────────────
        self._skip_warn = ctk.CTkFrame(w,
            fg_color=C["warn_bg"], border_color=C["warn_border"],
            border_width=1, corner_radius=RADIUS)
        self._skip_warn_lbl = ctk.CTkLabel(self._skip_warn,
            text="", font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["yellow"], wraplength=840, justify="left")
        self._skip_warn_lbl.pack(padx=PAD, pady=10)
        self._skip_warn.pack_forget()

        # ── EXIF Inspector ────────────────────────────────────
        self._inspector_card = Card(w,
            "EXIF Inspector — verify metadata before & after processing")
        ib = self._inspector_card.body()

        ir = ctk.CTkFrame(ib, fg_color="transparent")
        ir.pack(fill="x")
        self._inspector_entry = ctk.CTkEntry(ir,
            placeholder_text="Paste a relative image path, e.g.  2024/IMG_001.jpg",
            font=ctk.CTkFont(family="Courier New", size=11),
            fg_color=C["surface2"], border_color=C["border"],
            text_color=C["text"], height=34)
        self._inspector_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        SecBtn(ir, "🔍  Inspect", command=self._run_inspector).pack(side="right")

        self._inspector_result = ctk.CTkTextbox(ib,
            height=155, fg_color="#0a0a0c",
            border_color=C["border"], border_width=1,
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color=C["muted"], state="disabled", corner_radius=8)
        self._inspector_result.pack(fill="x", pady=(8, 0))

        ctk.CTkLabel(ib,
            text="Shows current EXIF in the file vs what the JSON sidecar contains. "
                 "Run again after processing to confirm the write succeeded.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=C["muted"]).pack(anchor="w", pady=(4, 0))
        self._inspector_card.pack_forget()

        # ── Step 2: Metadata Options ─────────────────────────
        c2 = Card(w, "Step 2 — Metadata Options")
        c2.pack(fill="x", padx=PAD, pady=(PAD, 0))
        b2 = c2.body()

        self._opt_force = ToggleRow(b2,
            "Force overwrite existing EXIF fields",
            desc="OFF = only fills missing fields (safe default).  "
                 "ON = overwrites everything from JSON even if the image already has dates/GPS.",
            default=False)
        self._opt_force.pack(fill="x", pady=(0, 6))
        _div(b2)

        self._opt_gps = ToggleRow(b2, "Embed GPS coordinates",
            desc="Only embeds if lat/lng are non-zero in the JSON.", default=True)
        self._opt_gps.pack(fill="x", pady=6)
        _div(b2)

        self._opt_people = ToggleRow(b2, "Embed people names",
            desc="Written to EXIF Artist / XPComment fields.", default=True)
        self._opt_people.pack(fill="x", pady=(6, 0))

        # ── Step 3: Output & Cleanup ─────────────────────────
        c3 = Card(w, "Step 3 — Output & Cleanup")
        c3.pack(fill="x", padx=PAD, pady=(PAD, 0))
        b3 = c3.body()

        self._opt_delete_json = ToggleRow(b3,
            "Delete JSON sidecar files after processing",
            desc="Removes .supplemental-metadata.json files once metadata is embedded. "
                 "Files that were skipped or errored keep their JSON.",
            default=True)
        self._opt_delete_json.pack(fill="x", pady=(0, 6))

        # ── Step 4: Organise ─────────────────────────────────
        c4 = Card(w, "Step 4 — Organise by Date  (optional)")
        c4.pack(fill="x", padx=PAD, pady=(PAD, 0))
        b4 = c4.body()

        self._opt_organise = ToggleRow(b4,
            "Organise files into dated folders",
            desc="Moves processed images into a folder structure based on photo date taken.",
            default=False)
        self._opt_organise.pack(fill="x")
        self._opt_organise._switch.configure(command=self._toggle_organise)

        self._org_sub = ctk.CTkFrame(b4, fg_color="transparent")
        ctk.CTkLabel(self._org_sub, text="Folder structure:",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=C["muted"]).pack(anchor="w", pady=(8, 4))

        self._org_var = ctk.StringVar(value="Year / Month")
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

        self._org_preview = ctk.CTkTextbox(self._org_sub,
            height=80, fg_color="#0a0a0c",
            border_color=C["border"], border_width=1,
            font=ctk.CTkFont(family="Courier New", size=10),
            text_color=C["blue"], state="disabled", corner_radius=8)
        self._org_preview.pack(fill="x", pady=(8, 0))
        self._update_org_preview()
        self._org_sub.pack_forget()

        # ── Step 5: Advanced Options ─────────────────────────
        c5 = Card(w, "Step 5 — Advanced Options  (optional)")
        c5.pack(fill="x", padx=PAD, pady=(PAD, 0))
        b5 = c5.body()

        self._opt_sanitise = ToggleRow(b5,
            "Sanitise filenames — rename cryptic files by date",
            desc="Renames files like AF1Qip_abc123.jpg → 2024-03-15_001.jpg. "
                 "Only renames if filename doesn't already contain a date.",
            default=False)
        self._opt_sanitise.pack(fill="x", pady=(0, 6))
        _div(b5)

        self._opt_resume = ToggleRow(b5,
            "Resume interrupted runs",
            desc="Remembers which files were already processed. "
                 "If a run is cancelled, the next run continues from where it stopped.",
            default=True)
        self._opt_resume.pack(fill="x", pady=(6, 6))
        _div(b5)

        tz_row = ctk.CTkFrame(b5, fg_color="transparent")
        tz_row.pack(fill="x", pady=(6, 0))
        tz_txt = ctk.CTkFrame(tz_row, fg_color="transparent")
        tz_txt.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(tz_txt, text="Timezone offset (hours from UTC)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=C["text"]).pack(anchor="w")
        ctk.CTkLabel(tz_txt,
            text="Google timestamps are UTC. Set your offset so dates are written correctly.\n"
                 "Pakistan = +5.0 | India = +5.5 | UK = 0 | US Eastern = -5",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=C["muted"], justify="left").pack(anchor="w")
        self._tz_var = ctk.StringVar(value="+5.0")
        ctk.CTkEntry(tz_row, textvariable=self._tz_var,
            width=70, font=ctk.CTkFont(family="Courier New", size=12),
            fg_color=C["surface2"], border_color=C["border"],
            text_color=C["text"], justify="center",
            height=32).pack(side="right", padx=(8, 0))

        # ── Step 6: Process ──────────────────────────────────
        c6 = Card(w, "Step 6 — Process")
        c6.pack(fill="x", padx=PAD, pady=(PAD, 0))
        b6 = c6.body()

        btn_row = ctk.CTkFrame(b6, fg_color="transparent")
        btn_row.pack(anchor="w")

        self._run_btn = PrimaryBtn(btn_row, "▶   Start Processing",
            command=self._start_processing)
        self._run_btn.pack(side="left", padx=(0, 8))
        self._run_btn.configure(state="disabled")

        self._dry_run_btn = SecBtn(btn_row, "🔬  Dry Run",
            command=self._start_dry_run)
        self._dry_run_btn.pack(side="left", padx=(0, 8))
        self._dry_run_btn.configure(state="disabled")

        self._clear_btn = SecBtn(btn_row, "✕  Clear",
            command=self._clear)
        self._clear_btn.pack(side="left")
        self._clear_btn.configure(state="disabled")

        # ── Progress (always in layout, hidden initially) ────
        self._progress_frame = ctk.CTkFrame(w, fg_color="transparent")
        ctk.CTkLabel(self._progress_frame,
            text="PROCESSING…",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=C["muted"]).pack(anchor="w", padx=PAD, pady=(PAD, 4))
        self._progress_bar = ctk.CTkProgressBar(self._progress_frame,
            fg_color=C["surface2"], progress_color=C["accent"],
            height=6, corner_radius=99)
        self._progress_bar.pack(fill="x", padx=PAD)
        self._progress_bar.set(0)
        self._progress_lbl = ctk.CTkLabel(self._progress_frame,
            text="0 / 0",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C["muted"])
        self._progress_lbl.pack(anchor="w", padx=PAD, pady=(4, PAD))
        self._progress_frame.pack_forget()

        # ── Done banner (always in layout, hidden initially) ─
        self._done_banner = ctk.CTkFrame(w,
            fg_color=C["ok_bg"], border_color=C["ok_border"],
            border_width=1, corner_radius=RADIUS)
        self._done_lbl = ctk.CTkLabel(self._done_banner,
            text="", font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=C["green"])
        self._done_lbl.pack(padx=PAD, pady=12)
        self._done_banner.pack_forget()

        # ── Stats bar (always in layout, hidden initially) ───
        self._stats_frame = ctk.CTkFrame(w, fg_color="transparent")
        sr = ctk.CTkFrame(self._stats_frame, fg_color="transparent")
        sr.pack(fill="x", padx=PAD, pady=(0, PAD))
        sr.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)
        self._s_written = StatCard(sr, "Metadata written", C["green"])
        self._s_skipped = StatCard(sr, "Already complete",  C["yellow"])
        self._s_nojson  = StatCard(sr, "No JSON sidecar",   C["blue"])
        self._s_errors  = StatCard(sr, "Errors",            C["red"])
        self._s_total   = StatCard(sr, "Total scanned",     C["accent2"])
        for i, s in enumerate([self._s_written, self._s_skipped,
                                self._s_nojson, self._s_errors, self._s_total]):
            s.grid(row=0, column=i, padx=4, sticky="ew")
        self._stats_frame.pack_forget()

        # ── Log (always in layout, hidden initially) ─────────
        self._log_frame = ctk.CTkFrame(w, fg_color="transparent")
        lh = ctk.CTkFrame(self._log_frame, fg_color="transparent")
        lh.pack(fill="x", padx=PAD, pady=(0, 6))
        ctk.CTkLabel(lh, text="ACTIVITY LOG",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=C["muted"]).pack(side="left")
        ctk.CTkLabel(lh, text="LIVE",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            fg_color=C["accent"], text_color="#fff",
            corner_radius=4, padx=6, pady=1).pack(side="left", padx=6)

        self._log_box = ctk.CTkTextbox(self._log_frame,
            height=280, fg_color="#0a0a0c",
            border_color=C["border"], border_width=1,
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color=C["muted"], corner_radius=8, state="disabled")
        self._log_box.pack(fill="x", padx=PAD)
        tb = self._log_box._textbox
        tb.tag_configure("ok",   foreground=C["green"])
        tb.tag_configure("skip", foreground=C["yellow"])
        tb.tag_configure("err",  foreground=C["red"])
        tb.tag_configure("info", foreground=C["blue"])
        tb.tag_configure("dim",  foreground=C["muted"])
        tb.tag_configure("dry",  foreground=C["accent2"])

        lb_row = ctk.CTkFrame(self._log_frame, fg_color="transparent")
        lb_row.pack(fill="x", padx=PAD, pady=(8, PAD))
        SecBtn(lb_row, "💾  Save log as .txt",
            command=self._save_log).pack(side="left", padx=(0, 8))
        SecBtn(lb_row, "📄  Open Report",
            command=self._open_report).pack(side="left")
        self._log_frame.pack_forget()

        # Bottom padding
        ctk.CTkFrame(w, fg_color="transparent", height=40).pack()

    # ─────────────────────────────────────────────────────────
    #  Toggle helpers
    # ─────────────────────────────────────────────────────────

    def _toggle_organise(self):
        if self._opt_organise.value:
            self._org_sub.pack(fill="x", pady=(4, 0))
        else:
            self._org_sub.pack_forget()

    def _update_org_preview(self, *_):
        v = self._org_var.get()
        if v == "Year only":
            t = "📁 2024/\n  └─ IMG_001.jpg\n  └─ IMG_002.jpg\n📁 2023/\n  └─ Photo_005.jpg"
        elif v == "Year / Month":
            t = "📁 2024/\n  📁 03 - March/\n    └─ IMG_001.jpg\n    └─ IMG_002.jpg\n  📁 11 - November/\n    └─ Photo_005.jpg"
        else:
            t = "📁 2024/\n  📁 03 - March/\n    📁 15/\n      └─ IMG_001.jpg\n    📁 16/\n      └─ IMG_002.jpg"
        self._org_preview.configure(state="normal")
        self._org_preview.delete("0.0", "end")
        self._org_preview.insert("0.0", t)
        self._org_preview.configure(state="disabled")

    # ─────────────────────────────────────────────────────────
    #  Folder scan
    # ─────────────────────────────────────────────────────────

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Select your Google Takeout folder")
        if not path:
            return
        self._folder_path = path
        self._folder_lbl.configure(
            text=path if len(path) < 72 else "…" + path[-69:],
            text_color=C["text"])
        self._scan_folder()

    def _scan_folder(self):
        # Show log so scan messages are visible
        self._log_frame.pack(fill="x", pady=(PAD, 0))
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

        if self._opt_resume.value:
            self._processed_set = load_state(self._folder_path)
        else:
            self._processed_set = set()

        matched = stats["matched_json"]
        total   = stats["total_media"]
        no_json = stats["no_json"]

        info_txt = (f"  {total} media files  ·  {matched} JSON sidecars matched  ·  "
                    f"{no_json} without JSON")
        if rf:
            info_txt += f"  ·  {len(rf)} RAW files (skipped safely)"

        self._folder_info_lbl.configure(text=info_txt)
        self._folder_info.pack(fill="x", pady=(8, 0))

        # Skip warning
        warned = stats.get("warned", {})
        if warned:
            labels = {".heic":"HEIC",".png":"PNG",".webp":"WebP",
                      ".mp4":"MP4",".mov":"MOV",".tiff":"TIFF",
                      ".jfif":"JFIF",".gif":"GIF",".bmp":"BMP"}
            parts = [f"{c} {labels.get(e, e.upper())}" for e, c in warned.items()]
            self._skip_warn_lbl.configure(
                text=f"⚠  Non-processable files with JSON sidecars: {', '.join(parts)}\n"
                     f"These formats have JSON but cannot have EXIF embedded and will be skipped.")
            self._skip_warn.pack(fill="x", padx=PAD, pady=(PAD, 0))
        else:
            self._skip_warn.pack_forget()

        # Inspector card
        if mf:
            self._inspector_entry.configure(placeholder_text=mf[0])
        self._inspector_card.pack(fill="x", padx=PAD, pady=(PAD, 0))

        if total > 0:
            self._run_btn.configure(state="normal")
            self._dry_run_btn.configure(state="normal")
        self._clear_btn.configure(state="normal")

        self._log(
            f"Scan complete — {total} media files, {matched} matched to JSON sidecars.",
            "info")

    # ─────────────────────────────────────────────────────────
    #  EXIF Inspector
    # ─────────────────────────────────────────────────────────

    def _run_inspector(self):
        path = self._inspector_entry.get().strip()
        if not path:
            self._iwrite("Enter a relative image path first.")
            return

        norm = path.replace("\\", "/")
        found_rel = found_abs = None
        for rel, absp in self._all_files.items():
            if rel.replace("\\", "/") == norm:
                found_rel, found_abs = rel, absp
                break

        if not found_abs:
            self._iwrite(f"File not found in loaded folder:\n  {path}")
            return

        lines = []
        ext = os.path.splitext(found_abs.lower())[1]

        if ext in {".jpg",".jpeg",".jfif",".jpe",
                   ".tiff",".tif",".webp",".heic",".heif"}:
            try:
                import piexif
                from PIL import Image
                if ext in {".heic",".heif"}:
                    try:
                        import pillow_heif
                        pillow_heif.register_heif_opener()
                    except ImportError:
                        pass
                img = Image.open(found_abs)
                eb  = img.info.get("exif", b"")
                ed  = piexif.load(eb) if eb else {}
                img.close()
                ifd0 = ed.get("0th", {})
                exif = ed.get("Exif", {})
                gps  = ed.get("GPS",  {})

                def _v(d, tag):
                    v = d.get(tag)
                    if v is None: return "(not set)"
                    if isinstance(v, bytes):
                        try: return v.decode("utf-8").strip("\x00")
                        except: return repr(v)
                    return str(v)

                lines.append("── EXIF in file ──────────────────────────")
                lines.append(f"DateTimeOriginal   {_v(exif, piexif.ExifIFD.DateTimeOriginal)}")
                lines.append(f"ImageDescription   {_v(ifd0, piexif.ImageIFD.ImageDescription)}")
                lines.append(f"Artist             {_v(ifd0, piexif.ImageIFD.Artist)}")
                glat = gps.get(piexif.GPSIFD.GPSLatitude)
                lines.append(f"GPS                {'set' if glat else '(not set)'}")
            except Exception as e:
                lines.append(f"Could not read EXIF: {e}")
        else:
            lines.append("(EXIF read not supported for this format in inspector)")

        json_rel = self._json_map.get(found_rel)
        if json_rel:
            json_abs = os.path.join(self._folder_path, json_rel)
            try:
                import json as _j
                with open(json_abs, "r", encoding="utf-8") as f:
                    meta = _j.load(f)
                lines += ["", "── JSON sidecar ──────────────────────────"]
                pt = meta.get("photoTakenTime", {})
                lines.append(f"photoTakenTime     {pt.get('formatted','(none)')}")
                geo = meta.get("geoData", {})
                lat, lng = geo.get("latitude",0), geo.get("longitude",0)
                lines.append(f"geoData            "
                    + (f"{lat:.6f}, {lng:.6f}" if lat or lng else "(no GPS)"))
                desc = meta.get("description","").strip()
                lines.append(f"description        {desc or '(empty)'}")
                ppl = meta.get("people",[])
                if ppl:
                    lines.append(f"people             "
                        + ", ".join(p.get("name","") for p in ppl))
            except Exception as e:
                lines.append(f"Could not read JSON: {e}")
        else:
            lines += ["", "No JSON sidecar matched for this file."]

        self._iwrite("\n".join(lines))

    def _iwrite(self, text):
        self._inspector_result.configure(state="normal")
        self._inspector_result.delete("0.0", "end")
        self._inspector_result.insert("0.0", text)
        self._inspector_result.configure(state="disabled")

    # ─────────────────────────────────────────────────────────
    #  Processing
    # ─────────────────────────────────────────────────────────

    def _start_processing(self):
        self._run_with_opts(dry_run=False)

    def _start_dry_run(self):
        self._run_with_opts(dry_run=True)

    def _run_with_opts(self, dry_run=False):
        if self._processing or not self._folder_path or not self._media_files:
            return

        try:
            tz = float(self._tz_var.get())
        except ValueError:
            tz = 0.0

        org_map = {
            "Year only":          "year",
            "Year / Month":       "year-month",
            "Year / Month / Day": "year-month-day",
        }

        opts = {
            "force":         self._opt_force.value,
            "embed_gps":     self._opt_gps.value,
            "embed_people":  self._opt_people.value,
            "delete_json":   self._opt_delete_json.value and not dry_run,
            "dry_run":       dry_run,
            "organise":      self._opt_organise.value,
            "org_structure": org_map.get(self._org_var.get(), "year-month"),
            "sanitise":      self._opt_sanitise.value,
            "resume":        self._opt_resume.value,
            "tz_offset":     tz,
        }

        self._processing = True
        self._run_btn.configure(state="disabled")
        self._dry_run_btn.configure(state="disabled")
        self._clear_btn.configure(state="disabled")
        self._done_banner.pack_forget()

        self._progress_frame.pack(fill="x", padx=PAD, pady=(PAD, 0))
        self._stats_frame.pack(fill="x", pady=(0, 0))
        self._log_frame.pack(fill="x", pady=(0, PAD))

        self._log_clear()
        mode = "DRY RUN" if dry_run else "Processing"
        self._log(f"[SnapMbed] {mode} — {len(self._media_files)} media files", "info")

        threading.Thread(
            target=self._process_thread,
            args=(opts,), daemon=True).start()

    def _process_thread(self, opts):
        from core.embedder  import process_file
        from core.organiser import organised_path, sanitise_filename, move_file, rename_file
        from core.cleaner   import delete_sidecar, save_state
        from core.reporter  import generate_report

        total     = len(self._media_files)
        written   = skipped = no_json = errors = 0
        json_del  = organised = renamed = 0
        log_entries    = []
        san_counter    = {}
        processed_set  = self._processed_set.copy()

        for i, rel in enumerate(self._media_files):
            abs_p = os.path.join(self._folder_path, rel)
            pct   = (i + 1) / total
            fname = os.path.basename(rel)
            self.after(0, self._upd_progress, pct, i+1, total, fname)

            if opts["resume"] and rel in processed_set:
                skipped += 1
                self.after(0, self._log, f"  [skip] {rel} — already processed", "skip")
                self.after(0, self._upd_stats, written, skipped, no_json, errors, total)
                continue

            json_rel = self._json_map.get(rel)
            if not json_rel:
                no_json += 1
                log_entries.append(("no_json", rel))
                self.after(0, self._log, f"  [no json] {rel}", "dim")
                self.after(0, self._upd_stats, written, skipped, no_json, errors, total)
                continue

            json_abs = os.path.join(self._folder_path, json_rel)
            result   = process_file(abs_p, json_abs, opts, self._folder_path)
            cur_abs  = abs_p

            if result["status"] in ("ok", "dry"):
                written += 1
                ts    = result.get("ts_used")
                tag   = "dry" if result["status"] == "dry" else "ok"
                label = "[dry]" if result["status"] == "dry" else "[✓]"
                line  = f"  {label} {rel}"

                if opts["sanitise"] and not opts["dry_run"]:
                    dk = ts[:8] if ts else "undated"
                    san_counter[dk] = san_counter.get(dk, 0) + 1
                    nn = sanitise_filename(fname, ts, san_counter[dk], opts["tz_offset"])
                    if nn != fname:
                        cur_abs = rename_file(cur_abs, nn)
                        renamed += 1
                        line += f"  →  {nn}"

                if opts["organise"] and ts:
                    new_rel  = organised_path(ts, rel, opts["org_structure"], opts["tz_offset"])
                    dest_abs = os.path.join(self._folder_path, new_rel)
                    if not opts["dry_run"] and dest_abs != cur_abs:
                        move_file(cur_abs, dest_abs)
                        organised += 1
                        line += f"  →  {new_rel}"

                self.after(0, self._log, line, tag)

                if opts["delete_json"] and os.path.exists(json_abs):
                    if delete_sidecar(json_abs, opts["dry_run"]):
                        json_del += 1

                processed_set.add(rel)
                log_entries.append(("ok", rel))

            elif result["status"] == "skip":
                skipped += 1
                self.after(0, self._log, f"  [skip] {rel} — {result['msg']}", "skip")
                log_entries.append(("skip", rel))
            else:
                errors += 1
                msg = f"  [ERR] {rel} — {result['msg']}"
                self.after(0, self._log, msg, "err")
                log_entries.append(("err", msg))

            self.after(0, self._upd_stats, written, skipped, no_json, errors, total)

        if opts["resume"] and not opts["dry_run"]:
            save_state(self._folder_path, processed_set)

        run_stats = dict(total=total, written=written, skipped=skipped,
                         no_json=no_json, errors=errors,
                         json_deleted=json_del, organised=organised, renamed=renamed)

        rpath = None
        if not opts["dry_run"]:
            rpath = generate_report(self._folder_path, run_stats, log_entries, opts)

        self.after(0, self._done,
                   written, skipped, no_json, errors,
                   json_del, organised, renamed, opts["dry_run"], rpath)

    # ─────────────────────────────────────────────────────────
    #  Thread-safe UI updaters
    # ─────────────────────────────────────────────────────────

    def _upd_progress(self, pct, cur, total, fname):
        self._progress_bar.set(pct)
        self._progress_lbl.configure(text=f"{cur} / {total} — {fname}")

    def _upd_stats(self, written, skipped, no_json, errors, total):
        self._s_written.set(written)
        self._s_skipped.set(skipped)
        self._s_nojson.set(no_json)
        self._s_errors.set(errors)
        self._s_total.set(total)

    def _done(self, written, skipped, no_json, errors,
              json_del, organised, renamed, dry_run, rpath):
        self._processing  = False
        self._report_path = rpath
        self._progress_bar.set(1.0)
        self._progress_lbl.configure(text="Done!")

        mode  = "Dry run complete" if dry_run else "Done!"
        parts = [
            f"{written} {'would be ' if dry_run else ''}written",
            f"{skipped} skipped", f"{no_json} no JSON", f"{errors} errors",
        ]
        if json_del:  parts.append(f"{json_del} JSON deleted")
        if organised: parts.append(f"{organised} organised")
        if renamed:   parts.append(f"{renamed} renamed")

        self._done_lbl.configure(text=f"✅  {mode}   {'  ·  '.join(parts)}")
        self._done_banner.pack(fill="x", padx=PAD, pady=(PAD, 0))

        self._log("", "dim")
        self._log("[SnapMbed] Finished.  " + "  ".join(parts), "info")
        if rpath:
            self._log(f"[SnapMbed] Report → {rpath}", "info")

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
        p = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files","*.txt")],
            initialfile="snapmbed_log.txt")
        if not p: return
        self._log_box.configure(state="normal")
        txt = self._log_box.get("0.0", "end")
        self._log_box.configure(state="disabled")
        with open(p, "w", encoding="utf-8") as f:
            f.write(txt)

    def _open_report(self):
        if self._report_path and os.path.exists(self._report_path):
            os.startfile(self._report_path)
        else:
            self._log("No report yet — run processing first.", "skip")

    def _clear(self):
        self._folder_path   = None
        self._all_files     = {}
        self._json_map      = {}
        self._media_files   = []
        self._raw_files     = []
        self._processed_set = set()
        self._report_path   = None

        self._folder_lbl.configure(text="No folder selected", text_color=C["muted"])
        self._folder_info.pack_forget()
        self._skip_warn.pack_forget()
        self._inspector_card.pack_forget()
        self._progress_frame.pack_forget()
        self._stats_frame.pack_forget()
        self._done_banner.pack_forget()
        self._log_frame.pack_forget()
        self._log_clear()

        self._progress_bar.set(0)
        self._progress_lbl.configure(text="0 / 0")
        for s in [self._s_written,self._s_skipped,
                  self._s_nojson,self._s_errors,self._s_total]:
            s.set(0)

        self._run_btn.configure(state="disabled")
        self._dry_run_btn.configure(state="disabled")
        self._clear_btn.configure(state="disabled")

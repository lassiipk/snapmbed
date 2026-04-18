"""
gui.py — Tkinter GUI for the metadata restore tool.
Simple, clean, functional. No luxury — just clarity.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
from pathlib import Path

from core.engine import Engine, RunConfig
from core.metadata import MetadataConfig, FieldConfig, check_exiftool


FIELD_LABELS = {
    "photo_taken_date": "Photo Taken Date",
    "creation_date":    "Upload/Creation Date",
    "gps":              "GPS Location",
    "description":      "Description",
    "title":            "Title",
    "people":           "People (Person Tags)",
    "google_url":       "Google Photos URL",
}

FIELD_DEFAULTS_ENABLED = {
    "photo_taken_date": True,
    "creation_date":    False,
    "gps":              True,
    "description":      True,
    "title":            True,
    "people":           True,
    "google_url":       False,
}

CONFLICT_OPTIONS = ["skip", "overwrite", "prefer_newer"]
GPS_ZERO_OPTIONS = ["skip", "overwrite_empty", "warn", "leave"]
UNMATCHED_OPTIONS = ["keep", "move", "delete"]
OUTPUT_OPTIONS = ["inplace", "separate"]
TIMEZONE_OPTIONS = ["utc", "local", "Asia/Karachi", "Asia/Dubai", "Europe/London",
                    "Europe/Berlin", "America/New_York", "America/Los_Angeles",
                    "Australia/Sydney", "Asia/Tokyo"]


class MetadataRestoreGUI:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Google Takeout — Metadata Restore Tool")
        self.root.resizable(True, True)
        self.root.minsize(720, 700)

        self._stop_flag = False
        self._running = False
        self._last_log_path = ""
        self._last_failed_path = ""

        # StringVars / BooleanVars
        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.output_mode_var = tk.StringVar(value="inplace")
        self.dry_run_var = tk.BooleanVar(value=False)
        self.backup_var = tk.BooleanVar(value=False)
        self.reprocess_var = tk.BooleanVar(value=False)
        self.verify_var = tk.BooleanVar(value=True)
        self.cleanup_progress_var = tk.BooleanVar(value=False)
        self.gps_zero_var = tk.StringVar(value="skip")
        self.timezone_var = tk.StringVar(value="utc")
        self.unmatched_var = tk.StringVar(value="keep")

        # Per-field enabled and conflict policy
        self.field_enabled = {
            name: tk.BooleanVar(value=FIELD_DEFAULTS_ENABLED[name])
            for name in FIELD_LABELS
        }
        self.field_conflict = {
            name: tk.StringVar(value="skip")
            for name in FIELD_LABELS
        }

        self._build_ui()
        self._check_exiftool_on_start()

    # ──────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Main scrollable canvas for the settings pane
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)  # log area expands

        row = 0

        # ── Folders ──
        folders_frame = ttk.LabelFrame(main_frame, text="  Folders  ", padding=8)
        folders_frame.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        folders_frame.columnconfigure(1, weight=1)
        self._build_folder_row(folders_frame, "Source Folder:", self.source_var, 0,
                                self._browse_source)
        self.output_row_widgets = self._build_folder_row(
            folders_frame, "Output Folder:", self.output_var, 1, self._browse_output
        )
        row += 1

        # ── Output Mode & Basic Options ──
        opts_frame = ttk.LabelFrame(main_frame, text="  Options  ", padding=8)
        opts_frame.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        opts_frame.columnconfigure(1, weight=1)

        ttk.Label(opts_frame, text="Output Mode:").grid(row=0, column=0, sticky="w", padx=4)
        om_frame = ttk.Frame(opts_frame)
        om_frame.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(om_frame, text="In-place", variable=self.output_mode_var,
                        value="inplace", command=self._toggle_output_folder).pack(side="left", padx=4)
        ttk.Radiobutton(om_frame, text="Separate output folder", variable=self.output_mode_var,
                        value="separate", command=self._toggle_output_folder).pack(side="left", padx=4)

        checks_frame = ttk.Frame(opts_frame)
        checks_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(checks_frame, text="Dry Run (simulate only)",
                        variable=self.dry_run_var).pack(side="left", padx=6)
        ttk.Checkbutton(checks_frame, text="Backup originals",
                        variable=self.backup_var).pack(side="left", padx=6)
        ttk.Checkbutton(checks_frame, text="Force reprocess",
                        variable=self.reprocess_var).pack(side="left", padx=6)
        ttk.Checkbutton(checks_frame, text="Verify after write",
                        variable=self.verify_var).pack(side="left", padx=6)
        ttk.Checkbutton(checks_frame, text="Clean up progress file",
                        variable=self.cleanup_progress_var).pack(side="left", padx=6)
        row += 1

        # ── Fields ──
        fields_frame = ttk.LabelFrame(main_frame, text="  Fields to Write  ", padding=8)
        fields_frame.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        for col in range(3):
            fields_frame.columnconfigure(col * 3, weight=0)
        self._build_fields_section(fields_frame)
        row += 1

        # ── Policies ──
        policy_frame = ttk.LabelFrame(main_frame, text="  Policies  ", padding=8)
        policy_frame.grid(row=row, column=0, sticky="ew", pady=(0, 6))
        policy_frame.columnconfigure(1, weight=1)
        policy_frame.columnconfigure(3, weight=1)

        ttk.Label(policy_frame, text="GPS Zero/Missing:").grid(row=0, column=0, sticky="w", padx=4)
        ttk.Combobox(policy_frame, textvariable=self.gps_zero_var,
                     values=GPS_ZERO_OPTIONS, state="readonly", width=18
                     ).grid(row=0, column=1, sticky="w", padx=4)

        ttk.Label(policy_frame, text="Timezone:").grid(row=0, column=2, sticky="w", padx=(16, 4))
        tz_combo = ttk.Combobox(policy_frame, textvariable=self.timezone_var,
                                values=TIMEZONE_OPTIONS, width=22)
        tz_combo.grid(row=0, column=3, sticky="w", padx=4)

        ttk.Label(policy_frame, text="Unmatched JSONs:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        ttk.Combobox(policy_frame, textvariable=self.unmatched_var,
                     values=UNMATCHED_OPTIONS, state="readonly", width=18
                     ).grid(row=1, column=1, sticky="w", padx=4)
        row += 1

        # ── Config Save/Load ──
        config_frame = ttk.Frame(main_frame)
        config_frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        ttk.Button(config_frame, text="💾 Save Settings",
                   command=self._save_config).pack(side="left", padx=4)
        ttk.Button(config_frame, text="📂 Load Settings",
                   command=self._load_config).pack(side="left", padx=4)
        row += 1

        # ── Run Controls ──
        run_frame = ttk.Frame(main_frame)
        run_frame.grid(row=row, column=0, sticky="ew", pady=(2, 6))
        self.run_btn = ttk.Button(run_frame, text="▶  RUN", command=self._start_run,
                                   style="Accent.TButton", width=16)
        self.run_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(run_frame, text="⏹  STOP", command=self._stop_run,
                                    width=12, state="disabled")
        self.stop_btn.pack(side="left", padx=4)
        self.view_log_btn = ttk.Button(run_frame, text="📄 View Log",
                                        command=self._open_log, width=12, state="disabled")
        self.view_log_btn.pack(side="left", padx=4)
        self.open_output_btn = ttk.Button(run_frame, text="📂 Open Output",
                                           command=self._open_output_folder, width=14, state="disabled")
        self.open_output_btn.pack(side="left", padx=4)
        self.status_label = ttk.Label(run_frame, text="Ready.", foreground="gray")
        self.status_label.pack(side="left", padx=12)
        row += 1

        # ── Progress bar ──
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var,
                                             maximum=100, length=400)
        self.progress_bar.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        row += 1

        # ── Log output ──
        log_frame = ttk.LabelFrame(main_frame, text="  Log  ", padding=4)
        log_frame.grid(row=row, column=0, sticky="nsew", pady=(0, 4))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=12, wrap=tk.WORD,
            font=("Consolas", 9), state="disabled",
            background="#1e1e1e", foreground="#d4d4d4"
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.tag_config("error",   foreground="#f44747")
        self.log_text.tag_config("warning", foreground="#ce9178")
        self.log_text.tag_config("success", foreground="#6a9955")
        self.log_text.tag_config("info",    foreground="#d4d4d4")
        row += 1

        # ── Summary bar ──
        self.summary_var = tk.StringVar(value="")
        ttk.Label(main_frame, textvariable=self.summary_var,
                  font=("Segoe UI", 9, "bold"), foreground="#007acc"
                  ).grid(row=row, column=0, sticky="w", padx=4)

        self._toggle_output_folder()

    def _build_folder_row(self, parent, label, var, row, browse_cmd):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=3)
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky="ew", padx=4, pady=3)
        btn = ttk.Button(parent, text="Browse…", command=browse_cmd, width=10)
        btn.grid(row=row, column=2, padx=4, pady=3)
        return (entry, btn)

    def _build_fields_section(self, parent):
        """Build field toggles with per-field conflict dropdowns."""
        fields = list(FIELD_LABELS.items())
        cols = 2  # fields per row
        for i, (name, label) in enumerate(fields):
            col_base = (i % cols) * 4
            row_idx = i // cols

            cb = ttk.Checkbutton(parent, text=label, variable=self.field_enabled[name])
            cb.grid(row=row_idx, column=col_base, sticky="w", padx=(8, 2), pady=3)

            ttk.Label(parent, text="if exists:").grid(
                row=row_idx, column=col_base + 1, sticky="e", padx=2)
            combo = ttk.Combobox(parent, textvariable=self.field_conflict[name],
                                  values=CONFLICT_OPTIONS, state="readonly", width=12)
            combo.grid(row=row_idx, column=col_base + 2, sticky="w", padx=(2, 16), pady=3)

    # ──────────────────────────────────────────────
    # Browse handlers
    # ──────────────────────────────────────────────

    def _browse_source(self):
        folder = filedialog.askdirectory(title="Select Source Folder")
        if folder:
            self.source_var.set(folder)

    def _browse_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_var.set(folder)

    def _toggle_output_folder(self):
        state = "normal" if self.output_mode_var.get() == "separate" else "disabled"
        for widget in self.output_row_widgets:
            widget.configure(state=state)

    # ──────────────────────────────────────────────
    # Config save / load
    # ──────────────────────────────────────────────

    def _save_config(self):
        path = filedialog.asksaveasfilename(
            title="Save Settings",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        cfg = self._build_runconfig()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg.to_dict(), f, indent=2)
        messagebox.showinfo("Saved", f"Settings saved to:\n{path}")

    def _load_config(self):
        path = filedialog.askopenfilename(
            title="Load Settings",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cfg = RunConfig.from_dict(data)
            self._apply_runconfig_to_ui(cfg)
            messagebox.showinfo("Loaded", f"Settings loaded from:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config:\n{e}")

    def _apply_runconfig_to_ui(self, cfg: RunConfig):
        self.source_var.set(cfg.source_folder)
        self.output_var.set(cfg.output_folder)
        self.output_mode_var.set(cfg.output_mode)
        self.dry_run_var.set(cfg.dry_run)
        self.reprocess_var.set(cfg.force_reprocess)
        self.backup_var.set(cfg.metadata.backup_originals)
        self.verify_var.set(cfg.metadata.verify_after_write)
        self.gps_zero_var.set(cfg.metadata.gps_zero_policy)
        self.timezone_var.set(cfg.metadata.timezone)
        self.unmatched_var.set(cfg.unmatched_policy)
        for name in FIELD_LABELS:
            fc = getattr(cfg.metadata, name)
            self.field_enabled[name].set(fc.enabled)
            self.field_conflict[name].set(fc.conflict_policy)
        self._toggle_output_folder()

    # ──────────────────────────────────────────────
    # Build RunConfig from UI state
    # ──────────────────────────────────────────────

    def _build_runconfig(self) -> RunConfig:
        cfg = RunConfig()
        cfg.source_folder = self.source_var.get().strip()
        cfg.output_folder = self.output_var.get().strip()
        cfg.output_mode   = self.output_mode_var.get()
        cfg.dry_run       = self.dry_run_var.get()
        cfg.force_reprocess = self.reprocess_var.get()
        cfg.cleanup_progress_file = self.cleanup_progress_var.get()
        cfg.unmatched_policy = self.unmatched_var.get()

        m = cfg.metadata
        m.backup_originals   = self.backup_var.get()
        m.verify_after_write = self.verify_var.get()
        m.gps_zero_policy    = self.gps_zero_var.get()
        m.timezone           = self.timezone_var.get()

        for name in FIELD_LABELS:
            fc = FieldConfig(
                enabled=self.field_enabled[name].get(),
                conflict_policy=self.field_conflict[name].get()
            )
            setattr(m, name, fc)

        return cfg

    # ──────────────────────────────────────────────
    # Run / Stop
    # ──────────────────────────────────────────────

    def _start_run(self):
        if self._running:
            return

        cfg = self._build_runconfig()

        # Validate
        if not cfg.source_folder:
            messagebox.showerror("Missing Input", "Please select a source folder.")
            return
        if not Path(cfg.source_folder).exists():
            messagebox.showerror("Not Found", f"Source folder does not exist:\n{cfg.source_folder}")
            return
        if cfg.output_mode == "separate" and not cfg.output_folder:
            messagebox.showerror("Missing Input",
                                  "Please select an output folder for 'separate' mode.")
            return

        # Warn about delete policy
        if cfg.unmatched_policy == "delete":
            if not messagebox.askyesno(
                "Confirm Delete",
                "Unmatched JSON policy is set to DELETE.\n"
                "This will permanently delete JSON files with no matching media.\n\nContinue?"
            ):
                return

        self._stop_flag = False
        self._running = True
        self._clear_log()
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress_var.set(0)
        self.summary_var.set("")

        log_dir = Path(__file__).parent.parent

        def progress_callback(current, total, msg):
            if total > 0:
                pct = (current / total) * 100
                self.root.after(0, lambda: self.progress_var.set(pct))
            self.root.after(0, lambda: self.status_label.configure(text=msg[:60]))

        def log_callback(msg):
            self.root.after(0, lambda m=msg: self._append_log(m))

        def run_thread():
            try:
                engine = Engine(
                    config=cfg,
                    log_dir=log_dir,
                    progress_callback=progress_callback,
                    log_callback=log_callback,
                    stop_flag=lambda: self._stop_flag
                )
                result = engine.run()
                self.root.after(0, lambda: self._on_run_complete(result))
            except Exception as e:
                self.root.after(0, lambda: self._on_run_error(str(e)))

        threading.Thread(target=run_thread, daemon=True).start()

    def _stop_run(self):
        self._stop_flag = True
        self.status_label.configure(text="Stopping after current file…")
        self.stop_btn.configure(state="disabled")

    def _on_run_complete(self, result: dict):
        self._running = False
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.progress_var.set(100)

        if result.get("status") == "nothing_to_do":
            self.status_label.configure(text="No JSON files found.")
            messagebox.showinfo("Done", "No supplemental-metadata.json files found in the selected folder.")
            return

        stats = result.get("stats")
        if stats:
            summary = (
                f"✓ Done: {stats.processed}  "
                f"✗ Failed: {stats.failed}  "
                f"🗑 JSONs deleted: {stats.json_deleted}  "
                f"⚠ Unmatched: {stats.unmatched_json}"
            )
            self.summary_var.set(summary)
        self.status_label.configure(text="Complete.")

        self._last_log_path = result.get("log_path", "")
        self._last_failed_path = result.get("failed_path", "")

        # Enable post-run buttons
        if self._last_log_path:
            self.view_log_btn.configure(state="normal")
        cfg_output = self.output_var.get().strip()
        if cfg_output and self.output_mode_var.get() == "separate":
            self.open_output_btn.configure(state="normal")
        elif self.source_var.get().strip():
            self.open_output_btn.configure(state="normal")

        detail = ""
        if self._last_log_path:
            detail += f"Log file:\n{self._last_log_path}"
        if self._last_failed_path:
            detail += f"\n\nFailed files list:\n{self._last_failed_path}"
        if detail:
            messagebox.showinfo("Run Complete", detail)
        else:
            messagebox.showinfo("Run Complete", "Done! Check the log for details.")

    def _on_run_error(self, error: str):
        self._running = False
        self.run_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_label.configure(text="Error.")
        messagebox.showerror("Error", f"An unexpected error occurred:\n\n{error}")

    # ──────────────────────────────────────────────
    # Post-run helpers
    # ──────────────────────────────────────────────

    def _open_log(self):
        """Open the log file in the default text editor."""
        import os, subprocess
        path = getattr(self, "_last_log_path", "")
        if path and Path(path).exists():
            try:
                os.startfile(path)
            except AttributeError:
                subprocess.Popen(["notepad", path])
        else:
            messagebox.showinfo("No Log", "No log file found from the last run.")

    def _open_output_folder(self):
        """Open the output (or source) folder in Windows Explorer."""
        import subprocess
        folder = self.output_var.get().strip()
        if self.output_mode_var.get() != "separate" or not folder:
            folder = self.source_var.get().strip()
        if folder and Path(folder).exists():
            subprocess.Popen(["explorer", folder])
        else:
            messagebox.showinfo("Not Found", "Folder not found.")

    # ──────────────────────────────────────────────
    # Log helpers
    # ──────────────────────────────────────────────

    def _append_log(self, msg: str):
        self.log_text.configure(state="normal")
        # Determine tag
        msg_lower = msg.lower()
        if "[error]" in msg_lower or "failed" in msg_lower:
            tag = "error"
        elif "[warning]" in msg_lower or "warn" in msg_lower or "unmatched" in msg_lower:
            tag = "warning"
        elif "✓" in msg or "wrote" in msg_lower or "deleted" in msg_lower:
            tag = "success"
        else:
            tag = "info"

        self.log_text.insert(tk.END, msg + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    # ──────────────────────────────────────────────
    # exiftool check
    # ──────────────────────────────────────────────

    def _check_exiftool_on_start(self):
        available, version = check_exiftool()
        if not available:
            messagebox.showerror(
                "exiftool Not Found",
                "exiftool was not found on your system PATH.\n\n"
                "Please download it from:\n"
                "https://exiftool.org\n\n"
                "Extract exiftool.exe and add it to your system PATH,\n"
                "then restart this tool."
            )
        else:
            self._append_log(f"[INFO] exiftool version {version} found. Ready.")


def run_gui():
    root = tk.Tk()

    # Use a clean theme
    style = ttk.Style()
    available = style.theme_names()
    for preferred in ("vista", "winnative", "clam", "alt"):
        if preferred in available:
            style.theme_use(preferred)
            break

    app = MetadataRestoreGUI(root)
    root.mainloop()

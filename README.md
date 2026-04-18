# Google Takeout — Metadata Restore Tool

Bakes metadata from Google Takeout's `.supplemental-metadata.json` sidecar files back into your media files, then deletes the JSON. Safe, resumable, and fully configurable.

---

## Requirements

### 1. Python 3.9+
Download from https://www.python.org/downloads/  
✅ During install, check **"Add Python to PATH"**

### 2. exiftool (required — external tool)
Download from: **https://exiftool.org**

**Windows setup:**
1. Download `exiftool-XX.XX_64.zip`
2. Extract the zip — you'll get a file called `exiftool(-k).exe`
3. Rename it to `exiftool.exe`
4. Place it in `C:\Windows\` (or any folder on your PATH)
5. Open a new Command Prompt and type `exiftool -ver` to confirm

### 3. Python packages (optional)
```
pip install tqdm
```
`tqdm` gives you a nice progress bar in CLI mode. The tool works fine without it.

---

## Installation

```
# No installation needed — just extract the folder and run.
cd metadata-restore
python main.py
```

---

## Usage

### Interactive (double-click friendly)
```
python main.py
```
Will ask: GUI or CLI?

### Launch GUI directly
```
python main.py --gui
```

### Launch CLI directly
```
python main.py --cli --source "C:\Takeout" --dry-run
python main.py --cli --source "C:\Takeout"
python main.py --cli --source "C:\Takeout" --output "C:\Takeout_fixed" --output-mode separate
```

### Full CLI help
```
python main.py --cli --help
```

---

## CLI Options Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--source` | *(required)* | Source folder to process |
| `--output` | — | Output folder (required with `--output-mode separate`) |
| `--output-mode` | `inplace` | `inplace` or `separate` |
| `--dry-run` | off | Simulate everything, touch nothing |
| `--reprocess` | off | Force reprocess already-done files |
| `--backup` | off | Copy `.bak` of originals before writing |
| `--no-verify` | off | Skip post-write verification |
| `--cleanup-progress` | off | Delete progress file after run |
| `--no-date` | off | Skip writing photo taken date |
| `--write-creation` | off | Also write upload/creation date |
| `--no-gps` | off | Skip GPS |
| `--no-description` | off | Skip description |
| `--no-title` | off | Skip title |
| `--no-people` | off | Skip person tags |
| `--write-url` | off | Write Google Photos URL to metadata |
| `--conflict-*` | `skip` | Per-field conflict: `skip`, `overwrite`, `prefer_newer` |
| `--gps-zero-policy` | `skip` | `skip`, `overwrite_empty`, `warn`, `leave` |
| `--timezone` | `utc` | `utc`, `local`, or `Region/City` (e.g. `Asia/Karachi`) |
| `--unmatched-policy` | `keep` | `keep`, `move`, `delete` |
| `--config` | — | Load settings from a JSON file |
| `--save-config` | — | Save current settings to a JSON file and exit |
| `--log-dir` | script folder | Where to write log files |

---

## What Gets Written

| JSON Field | Written To |
|---|---|
| `photoTakenTime` | `DateTimeOriginal`, `CreateDate` |
| `creationTime` | `XMP:DateCreated` *(optional, off by default)* |
| `geoData` | `GPSLatitude`, `GPSLongitude`, `GPSAltitude` |
| `description` | `ImageDescription`, `XMP:Description` |
| `title` | `XMP:Title` |
| `people[].name` | `XMP:PersonInImage` |
| `url` | `XMP:Source` *(optional, off by default)* |

---

## Safety Guarantees

- ✅ JSON is **never deleted** unless the metadata write was verified
- ✅ Dry run **never** writes, modifies, or deletes anything
- ✅ Failed files are **always logged** — never silent
- ✅ Unmatched JSONs are **never auto-deleted** without explicit confirmation
- ✅ Progress is saved — interrupted runs resume where they left off

---

## Output Files

After a run, the tool creates in the **script folder**:

| File | Contents |
|---|---|
| `metadata_restore_YYYYMMDD_HHMMSS.log` | Full timestamped log of every action |
| `failed_files_YYYYMMDD_HHMMSS.txt` | Clean list of files that failed (if any) |

Inside your **source folder**:

| File | Contents |
|---|---|
| `._metadata_restore_progress.json` | Resume tracking (safe to delete after a complete run) |

---

## Folder Structure

```
metadata-restore/
├── main.py                  ← Entry point
├── requirements.txt
├── README.md
├── config/
│   └── defaults.json        ← Default settings
├── core/
│   ├── scanner.py           ← Recursive file discovery
│   ├── matcher.py           ← JSON ↔ media matching engine
│   ├── metadata.py          ← exiftool write logic
│   ├── progress.py          ← Resume/progress tracking
│   ├── reporter.py          ← Logging and reports
│   └── engine.py            ← Main processing pipeline
└── interfaces/
    ├── cli.py               ← CLI interface
    └── gui.py               ← Tkinter GUI
```

---

## Troubleshooting

**"exiftool not found"**  
→ Make sure `exiftool.exe` is on your PATH. Open a new terminal and try `exiftool -ver`.

**Files processed but dates still wrong in Windows Explorer**  
→ Windows Explorer uses file system timestamps, not EXIF. Use a photo viewer like IrfanView, FastStone, or the Photos app to see real EXIF dates.

**Progress file left behind**  
→ It's harmless. Enable "Clean up progress file" in settings or delete `._metadata_restore_progress.json` manually.

**Some JSONs show as unmatched**  
→ This means the tool couldn't find a media file for them. Use unmatched policy `move` to collect them in `_unmatched_review/` for manual inspection.

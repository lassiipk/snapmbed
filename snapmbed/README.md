# SnapMbed 🗂️

**Embed Google Takeout JSON metadata back into your photos — locally, privately, zero cloud.**

---

## What it does

When you export your photos from Google Photos via Google Takeout, the metadata (date taken, GPS, description, people tags) ends up in separate `.supplemental-metadata.json` files instead of inside the images themselves.

SnapMbed reads those JSON sidecars and writes the metadata directly into each photo's EXIF — so every image viewer, file manager, and photo app sees the correct dates and location without needing Google.

---

## Supported formats

| Format | Support |
|--------|---------|
| JPG / JPEG / JFIF | ✅ Full EXIF |
| WebP | ✅ Full EXIF |
| TIFF | ✅ Full EXIF |
| HEIC / HEIF | ✅ Full EXIF (requires pillow-heif) |
| PNG | ⚠️ Text chunks (not visible in Explorer) |
| MP4 / MOV | ⚠️ Date tag only |
| RAW (CR2/NEF/ARW etc.) | ⏭️ Skipped safely |

---

## Features

- ✅ Embeds date taken, GPS, description, title, people names
- ✅ Deletes JSON sidecars after processing (optional)
- ✅ Organise files into Year / Month / Day folder structure
- ✅ Sanitise cryptic filenames → `2024-03-15_001.jpg`
- ✅ Force overwrite OR merge (fill-in-missing) mode
- ✅ Dry run — simulate everything, write nothing
- ✅ Resume interrupted runs
- ✅ Timezone offset selector (Google timestamps are UTC)
- ✅ EXIF Inspector — see before/after metadata for any file
- ✅ Live color-coded log + summary report
- ✅ 100% offline — nothing leaves your machine

---

## Installation

```bash
pip install customtkinter Pillow piexif mutagen pillow-heif
python snapmbed.py
```

---

## Build standalone .exe (Windows)

```bash
pip install pyinstaller
pyinstaller build.spec
# Output: dist/snapmbed.exe  (~50MB, no Python needed)
```

---

## Project structure

```
snapmbed/
├── snapmbed.py        ← run this
├── core/
│   ├── scanner.py     ← finds files, builds JSON map
│   ├── embedder.py    ← writes metadata per format
│   ├── organiser.py   ← date folders + filename sanitiser
│   ├── cleaner.py     ← JSON deletion + resume state
│   └── reporter.py    ← summary report generator
├── gui/
│   ├── app.py         ← main CustomTkinter window
│   └── theme.py       ← colors, fonts, constants
└── requirements.txt
```

---

## License

MIT

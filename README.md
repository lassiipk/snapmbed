# SnapMbed

> Embed your Google Takeout metadata back where it belongs — inside your photos.

When you export photos from Google, the metadata (date taken, GPS, descriptions, people) ends up in separate `.json` sidecar files instead of inside the images themselves. SnapMbed fixes that — locally, privately, with zero installs.

---

## Features

- **Merge mode** — only fills in missing EXIF fields, never overwrites what's already there
- **In-place writing** — updates your files directly on disk (your original Takeout ZIP is your backup)
- **ZIP download** — optionally download all processed images as a ZIP
- **Recursive scanning** — handles nested year folders from Google Takeout automatically
- **Skips images that don't need it** — already-complete images are left untouched
- **Live log** — see exactly what happened to every file, saveable as `.txt`

## What gets embedded

| JSON field | Written to |
|---|---|
| `photoTakenTime` | EXIF `DateTimeOriginal` |
| `geoData` lat/lng | EXIF GPS tags |
| `description` | EXIF `ImageDescription` |
| `title` | EXIF `XPTitle` |
| `people[].name` | EXIF `Artist` / `XPComment` |

## How to use

1. Download `snapmbed.html`
2. Open it in any modern browser (Chrome, Edge, Firefox)
3. Select your Google Takeout folder
4. Click **Start Processing**

That's it. No installs. No internet. No data leaves your computer.

## Expected folder structure

Works with Google Takeout's default layout:

```
Takeout/
  2011/
    Photo0038.jpg
    Photo0038.jpg.json
  2023/
    IMG_001.jpg
    IMG_001.jpg.json
```

## Notes

- **JPEG/JPG only** — PNG and other formats don't have standardized EXIF support
- **Google Photos URLs** in the JSON are dead links once your account is deleted — they are safely ignored
- The tool only modifies files you explicitly select — nothing else on your disk is touched

## Built with

- Vanilla HTML + JavaScript — zero dependencies, zero network requests
- Everything bundled in a single `.html` file

---

Made with ❤️ for people taking back control of their photos.
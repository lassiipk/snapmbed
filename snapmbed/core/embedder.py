"""
core/embedder.py — writes metadata into image/video files.
"""
import os, json, struct, zlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from PIL import Image
    import piexif
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False

try:
    import mutagen.mp4
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

JPEG_EXTS = {".jpg", ".jpeg", ".jpe", ".jfif"}
HEIC_EXTS = {".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v"}


class EmbedResult:
    __slots__ = ("status", "msg", "path")
    def __init__(self, status, msg="", path=""):
        self.status = status
        self.msg = msg
        self.path = path


def _parse_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _ts_to_dt(ts, tz=0):
    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc) + timedelta(hours=tz)
    return dt.replace(tzinfo=None)

def _ts_to_exif_str(ts, tz=0):
    return _ts_to_dt(ts, tz).strftime("%Y:%m:%d %H:%M:%S")

def _dms(deg):
    d = abs(deg)
    degrees = int(d)
    minutes = int((d - degrees) * 60)
    seconds = round(((d - degrees) * 60 - minutes) * 60 * 10000)
    return [(degrees, 1), (minutes, 1), (seconds, 10000)]

def _xp(s):
    return list(s.encode("utf-16-le") + b"\x00\x00")


def _embed_piexif(abs_media, meta, opts):
    try:
        img = Image.open(abs_media)
        try:
            raw = img.info.get("exif", b"")
            ed = piexif.load(raw) if raw else {"0th": {}, "Exif": {}, "GPS": {}}
        except Exception:
            ed = {"0th": {}, "Exif": {}, "GPS": {}}
        for k in ("0th", "Exif", "GPS", "1st"):
            ed.setdefault(k, {})
        changed = False
        force = opts.get("force", False)
        tz = opts.get("tz_offset", 0)

        if meta.get("photoTakenTime", {}).get("timestamp"):
            tag = piexif.ExifIFD.DateTimeOriginal
            if force or tag not in ed["Exif"]:
                val = _ts_to_exif_str(meta["photoTakenTime"]["timestamp"], tz).encode()
                ed["Exif"][tag] = val
                ed["Exif"][piexif.ExifIFD.DateTimeDigitized] = val
                changed = True

        if opts.get("gps", True) and meta.get("geoData"):
            lat = meta["geoData"].get("latitude", 0)
            lng = meta["geoData"].get("longitude", 0)
            if (lat != 0 or lng != 0) and (force or piexif.GPSIFD.GPSLatitude not in ed["GPS"]):
                ed["GPS"][piexif.GPSIFD.GPSLatitudeRef]  = b"N" if lat >= 0 else b"S"
                ed["GPS"][piexif.GPSIFD.GPSLatitude]     = _dms(lat)
                ed["GPS"][piexif.GPSIFD.GPSLongitudeRef] = b"E" if lng >= 0 else b"W"
                ed["GPS"][piexif.GPSIFD.GPSLongitude]    = _dms(lng)
                changed = True

        if meta.get("description", "").strip():
            tag = piexif.ImageIFD.ImageDescription
            if force or tag not in ed["0th"]:
                ed["0th"][tag] = meta["description"].strip().encode("utf-8")
                changed = True

        if meta.get("title", "").strip():
            tag = piexif.ImageIFD.XPTitle
            if force or tag not in ed["0th"]:
                ed["0th"][tag] = _xp(meta["title"].strip())
                changed = True

        if opts.get("people", True) and meta.get("people"):
            names = ", ".join(p["name"] for p in meta["people"] if p.get("name"))
            if names and (force or piexif.ImageIFD.XPComment not in ed["0th"]):
                ed["0th"][piexif.ImageIFD.XPComment] = _xp(names)
                ed["0th"][piexif.ImageIFD.Artist] = names.encode("utf-8")
                changed = True

        if not changed:
            img.close()
            return EmbedResult("skip", "already complete")

        exif_bytes = piexif.dump(ed)
        ext = Path(abs_media).suffix.lower()
        if ext in JPEG_EXTS:
            piexif.insert(exif_bytes, abs_media)
        else:
            img.save(abs_media, exif=exif_bytes)
        img.close()
        return EmbedResult("ok", "", abs_media)
    except Exception as e:
        return EmbedResult("err", str(e))


def _embed_png(abs_media, meta, opts):
    try:
        with open(abs_media, "rb") as f:
            data = f.read()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            return EmbedResult("err", "Not a valid PNG")
        force = opts.get("force", False)
        tz = opts.get("tz_offset", 0)
        has_xmp = b"XML:com.adobe.xmp" in data
        if has_xmp and not force:
            return EmbedResult("skip", "already has XMP metadata")

        date_str = ""
        if meta.get("photoTakenTime", {}).get("timestamp"):
            dt = _ts_to_dt(meta["photoTakenTime"]["timestamp"], tz)
            date_str = dt.strftime("%Y-%m-%dT%H:%M:%S")

        desc = meta.get("description", "").strip()
        title = meta.get("title", "").strip()

        xmp = ('<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
               '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
               '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
               '<rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/" '
               'xmlns:dc="http://purl.org/dc/elements/1.1/" '
               'xmlns:exif="http://ns.adobe.com/exif/1.0/">\n')
        if date_str:
            xmp += f'  <xmp:CreateDate>{date_str}</xmp:CreateDate>\n'
            xmp += f'  <exif:DateTimeOriginal>{date_str}</exif:DateTimeOriginal>\n'
        if title:
            xmp += f'  <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{title}</rdf:li></rdf:Alt></dc:title>\n'
        if desc:
            xmp += f'  <dc:description><rdf:Alt><rdf:li xml:lang="x-default">{desc}</rdf:li></rdf:Alt></dc:description>\n'
        xmp += '</rdf:Description>\n</rdf:RDF>\n</x:xmpmeta>\n<?xpacket end="w"?>'
        xmp_bytes = xmp.encode("utf-8")

        kw = b"XML:com.adobe.xmp"
        chunk_data = kw + b"\x00\x00\x00\x00\x00" + xmp_bytes
        crc = zlib.crc32(b"iTXt" + chunk_data) & 0xFFFFFFFF
        chunk = struct.pack(">I", len(chunk_data)) + b"iTXt" + chunk_data + struct.pack(">I", crc)

        if date_str:
            td = b"Creation Time\x00" + date_str.encode()
            tc = zlib.crc32(b"tEXt" + td) & 0xFFFFFFFF
            chunk += struct.pack(">I", len(td)) + b"tEXt" + td + struct.pack(">I", tc)

        output = data[:8]
        pos = 8
        ihdr_done = False
        while pos < len(data) - 3:
            if pos + 8 > len(data):
                break
            length = struct.unpack(">I", data[pos:pos+4])[0]
            ctype = data[pos+4:pos+8]
            end = pos + 12 + length
            if end > len(data):
                output += data[pos:]
                break
            if ctype == b"IHDR":
                output += data[pos:end]
                if not ihdr_done:
                    output += chunk
                    ihdr_done = True
            elif ctype in (b"iTXt", b"tEXt") and (
                b"XML:com.adobe.xmp" in data[pos+8:end] or
                b"Creation Time" in data[pos+8:end]
            ):
                pass
            else:
                output += data[pos:end]
            pos = end

        with open(abs_media, "wb") as f:
            f.write(output)
        return EmbedResult("ok", "", abs_media)
    except Exception as e:
        return EmbedResult("err", str(e))


def _embed_video(abs_media, meta, opts):
    if not MUTAGEN_AVAILABLE:
        return EmbedResult("skip", "mutagen not installed")
    try:
        if not meta.get("photoTakenTime", {}).get("timestamp"):
            return EmbedResult("skip", "no timestamp in JSON")
        force = opts.get("force", False)
        tz = opts.get("tz_offset", 0)
        dt = _ts_to_dt(meta["photoTakenTime"]["timestamp"], tz)
        date_str = dt.strftime("%Y-%m-%dT%H:%M:%S")
        video = mutagen.mp4.MP4(abs_media)
        if not force and video.tags and "\xa9day" in video.tags:
            return EmbedResult("skip", "already has date tag")
        if video.tags is None:
            video.add_tags()
        video.tags["\xa9day"] = [date_str]
        if meta.get("description", "").strip():
            video.tags["\xa9cmt"] = [meta["description"].strip()]
        if meta.get("title", "").strip():
            video.tags["\xa9nam"] = [meta["title"].strip()]
        video.save()
        return EmbedResult("ok", "", abs_media)
    except Exception as e:
        return EmbedResult("err", str(e))


def embed_metadata(media_rel, json_rel, folder, opts):
    abs_media = os.path.join(folder, media_rel)
    abs_json  = os.path.join(folder, json_rel)
    if not os.path.exists(abs_media):
        return EmbedResult("err", f"File not found: {media_rel}")
    if not os.path.exists(abs_json):
        return EmbedResult("nojson", f"JSON not found")
    try:
        meta = _parse_json(abs_json)
    except Exception as e:
        return EmbedResult("err", f"Bad JSON: {e}")
    ext = Path(media_rel).suffix.lower()
    if ext in (JPEG_EXTS | {".webp", ".tiff", ".tif"} | HEIC_EXTS):
        if not PIL_AVAILABLE:
            return EmbedResult("err", "Pillow not installed")
        if ext in HEIC_EXTS and not HEIF_AVAILABLE:
            return EmbedResult("skip", "pillow-heif not installed — HEIC skipped")
        return _embed_piexif(abs_media, meta, opts)
    elif ext == ".png":
        return _embed_png(abs_media, meta, opts)
    elif ext in VIDEO_EXTS:
        return _embed_video(abs_media, meta, opts)
    return EmbedResult("skip", f"Unsupported: {ext}")


def get_current_metadata(abs_path):
    result = {}
    ext = Path(abs_path).suffix.lower()
    if not os.path.exists(abs_path):
        return {"error": "File not found"}
    try:
        if ext in (set(JPEG_EXTS) | {".webp", ".tiff", ".tif", ".heic", ".heif", ".png"}):
            if not PIL_AVAILABLE:
                return {"error": "Pillow not installed"}
            img = Image.open(abs_path)
            raw = img.info.get("exif", b"")
            if raw:
                try:
                    ed = piexif.load(raw)
                    e = ed.get("Exif", {}); g = ed.get("GPS", {}); ifd0 = ed.get("0th", {})
                    dto = e.get(piexif.ExifIFD.DateTimeOriginal)
                    if dto: result["DateTimeOriginal"] = dto.decode("utf-8", errors="replace")
                    desc = ifd0.get(piexif.ImageIFD.ImageDescription)
                    if desc: result["ImageDescription"] = desc.decode("utf-8", errors="replace")
                    artist = ifd0.get(piexif.ImageIFD.Artist)
                    if artist: result["Artist"] = artist.decode("utf-8", errors="replace")
                    if piexif.GPSIFD.GPSLatitude in g and piexif.GPSIFD.GPSLongitude in g:
                        def dms2dec(d): return d[0][0]/d[0][1]+d[1][0]/(d[1][1]*60)+d[2][0]/(d[2][1]*3600)
                        lat = dms2dec(g[piexif.GPSIFD.GPSLatitude])
                        lng = dms2dec(g[piexif.GPSIFD.GPSLongitude])
                        if g.get(piexif.GPSIFD.GPSLatitudeRef) in (b"S","S"): lat=-lat
                        if g.get(piexif.GPSIFD.GPSLongitudeRef) in (b"W","W"): lng=-lng
                        result["GPS"] = f"{lat:.6f}, {lng:.6f}"
                except Exception:
                    result["EXIF"] = "(could not parse)"
            else:
                result["EXIF"] = "(no EXIF data)"
            img.close()
        elif ext in {".mp4",".mov",".m4v"} and MUTAGEN_AVAILABLE:
            v = mutagen.mp4.MP4(abs_path)
            if v.tags:
                if "\xa9day" in v.tags: result["Creation Date"] = str(v.tags["\xa9day"][0])
                if "\xa9nam" in v.tags: result["Title"] = str(v.tags["\xa9nam"][0])
                if "\xa9cmt" in v.tags: result["Comment"] = str(v.tags["\xa9cmt"][0])
    except Exception as e:
        result["error"] = str(e)
    return result

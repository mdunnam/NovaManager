"""
EXIF metadata extraction for PhotoFlow.
Reads camera, lens, exposure, GPS data from image files using Pillow.
"""
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    Image = None
    TAGS = {}
    GPSTAGS = {}


def extract_exif(filepath: str) -> dict:
    """Extract EXIF metadata from an image file.

    Returns a flat dict with keys matching the photos table columns:
    exif_camera, exif_lens, exif_focal_length, exif_iso,
    exif_aperture, exif_shutter, exif_gps_lat, exif_gps_lon,
    exif_date_taken, image_width, image_height, file_size_kb.
    """
    result = {
        'exif_camera': '',
        'exif_lens': '',
        'exif_focal_length': '',
        'exif_iso': '',
        'exif_aperture': '',
        'exif_shutter': '',
        'exif_gps_lat': None,
        'exif_gps_lon': None,
        'exif_date_taken': None,
        'image_width': 0,
        'image_height': 0,
        'file_size_kb': 0,
    }

    try:
        path = Path(filepath)
        result['file_size_kb'] = int(path.stat().st_size / 1024)
    except Exception:
        pass

    if Image is None:
        return result

    try:
        img = Image.open(filepath)
        result['image_width'], result['image_height'] = img.size

        raw_exif = img._getexif()
        if not raw_exif:
            return result

        exif = {TAGS.get(k, k): v for k, v in raw_exif.items()}

        # Camera make/model
        make = str(exif.get('Make', '')).strip().rstrip('\x00')
        model = str(exif.get('Model', '')).strip().rstrip('\x00')
        if make and model and model.startswith(make):
            result['exif_camera'] = model
        elif make or model:
            result['exif_camera'] = f"{make} {model}".strip()

        # Lens
        lens = (
            exif.get('LensModel') or
            exif.get('LensSpecification') or
            exif.get('Lens') or ''
        )
        result['exif_lens'] = str(lens).strip().rstrip('\x00')

        # Focal length
        fl = exif.get('FocalLength')
        if fl:
            try:
                result['exif_focal_length'] = f"{float(fl):.0f}mm"
            except Exception:
                pass

        # ISO
        iso = exif.get('ISOSpeedRatings') or exif.get('ISO')
        if iso:
            result['exif_iso'] = str(iso)

        # Aperture
        aperture = exif.get('FNumber')
        if aperture:
            try:
                result['exif_aperture'] = f"f/{float(aperture):.1f}"
            except Exception:
                pass

        # Shutter speed
        shutter = exif.get('ExposureTime')
        if shutter:
            try:
                s = float(shutter)
                if s < 1:
                    result['exif_shutter'] = f"1/{int(round(1/s))}s"
                else:
                    result['exif_shutter'] = f"{s}s"
            except Exception:
                pass

        # Date taken
        for date_tag in ('DateTimeOriginal', 'DateTime', 'DateTimeDigitized'):
            dt_str = exif.get(date_tag)
            if dt_str:
                try:
                    result['exif_date_taken'] = datetime.strptime(
                        str(dt_str), '%Y:%m:%d %H:%M:%S'
                    )
                    break
                except Exception:
                    pass

        # GPS
        gps_info = exif.get('GPSInfo')
        if gps_info:
            gps = {GPSTAGS.get(k, k): v for k, v in gps_info.items()}
            lat = _gps_to_decimal(gps.get('GPSLatitude'), gps.get('GPSLatitudeRef'))
            lon = _gps_to_decimal(gps.get('GPSLongitude'), gps.get('GPSLongitudeRef'))
            if lat is not None:
                result['exif_gps_lat'] = lat
            if lon is not None:
                result['exif_gps_lon'] = lon

    except Exception as e:
        print(f"  [EXIF] Could not read {filepath}: {e}")

    return result


def _gps_to_decimal(coords, ref) -> float | None:
    """Convert GPS DMS tuple to decimal degrees."""
    if not coords or len(coords) < 3:
        return None
    try:
        deg = float(coords[0])
        mins = float(coords[1])
        secs = float(coords[2])
        decimal = deg + mins / 60 + secs / 3600
        if ref in ('S', 'W'):
            decimal = -decimal
        return round(decimal, 6)
    except Exception:
        return None


def format_exif_summary(photo: dict) -> str:
    """Return a readable one-line EXIF summary for a photo dict."""
    parts = []
    if photo.get('exif_camera'):
        parts.append(photo['exif_camera'])
    lens_parts = []
    if photo.get('exif_focal_length'):
        lens_parts.append(photo['exif_focal_length'])
    if photo.get('exif_aperture'):
        lens_parts.append(photo['exif_aperture'])
    if photo.get('exif_shutter'):
        lens_parts.append(photo['exif_shutter'])
    if photo.get('exif_iso'):
        lens_parts.append(f"ISO {photo['exif_iso']}")
    if lens_parts:
        parts.append(' · '.join(lens_parts))
    return ' — '.join(parts) if parts else 'No EXIF data'

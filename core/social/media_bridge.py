"""Helpers for staging local media into a publicly served folder.

The social APIs for Instagram, Pinterest, and Threads require a public image
URL. PhotoFlow stores local files, so this module bridges that gap by mapping a
configured local folder to a configured public base URL and, when necessary,
copying local files into that folder before posting.
"""
from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
import shutil
from urllib.parse import quote


@dataclass
class PublicMediaResult:
    """Result of preparing a local file for URL-based platform publishing."""

    success: bool
    public_url: str = ''
    staged_path: str = ''
    message: str = ''


def _safe_stem(name: str) -> str:
    """Sanitize a filename stem for staging into the publish media folder."""
    cleaned = []
    for ch in name.strip():
        if ch.isalnum() or ch in ('-', '_'):
            cleaned.append(ch)
        elif ch in (' ', '.'):
            cleaned.append('_')
    result = ''.join(cleaned).strip('_')
    return result[:64] or 'photo'


def describe_media_bridge(credentials: dict) -> tuple[bool, str]:
    """Return a human-readable status for the configured local-to-public mapping."""
    local_media_root = (credentials.get('local_media_root') or '').strip()
    public_image_base_url = (credentials.get('public_image_base_url') or '').strip().rstrip('/')

    if not local_media_root and not public_image_base_url:
        return False, 'Local file publishing bridge is not configured.'
    if not local_media_root:
        return False, 'Missing Local Media Root.'
    if not public_image_base_url:
        return False, 'Missing Public Image Base URL.'

    try:
        root = Path(local_media_root).expanduser().resolve()
    except Exception:
        return False, 'Invalid Local Media Root path.'
    return True, f'Local files will stage into {root} and publish from {public_image_base_url}'


def ensure_public_image(filepath: str, credentials: dict, platform: str) -> PublicMediaResult:
    """Return a public URL for a media file, copying it into the media root if needed."""
    if filepath.startswith('http://') or filepath.startswith('https://'):
        return PublicMediaResult(True, public_url=filepath, staged_path=filepath)

    bridge_ok, bridge_msg = describe_media_bridge(credentials)
    if not bridge_ok:
        return PublicMediaResult(False, message=bridge_msg)

    source_path = Path(filepath)
    if not source_path.exists():
        return PublicMediaResult(False, message=f'Local file not found: {filepath}')

    local_media_root = Path(credentials['local_media_root']).expanduser().resolve()
    public_base = credentials['public_image_base_url'].strip().rstrip('/')
    local_media_root.mkdir(parents=True, exist_ok=True)

    try:
        resolved_source = source_path.resolve()
    except Exception:
        resolved_source = source_path

    try:
        relative = resolved_source.relative_to(local_media_root)
        staged_path = resolved_source
    except ValueError:
        stamp = datetime.utcnow().strftime('%Y-%m-%d')
        stat = resolved_source.stat()
        digest = hashlib.sha1(
            f'{resolved_source}|{stat.st_mtime_ns}|{stat.st_size}'.encode('utf-8')
        ).hexdigest()[:10]
        staged_dir = local_media_root / platform.lower() / stamp
        staged_dir.mkdir(parents=True, exist_ok=True)
        suffix = resolved_source.suffix or '.jpg'
        staged_path = staged_dir / f'{_safe_stem(resolved_source.stem)}_{digest}{suffix.lower()}'
        if not staged_path.exists():
            shutil.copy2(resolved_source, staged_path)
        relative = staged_path.relative_to(local_media_root)

    public_url = public_base + '/' + '/'.join(quote(part) for part in relative.parts)
    return PublicMediaResult(True, public_url=public_url, staged_path=str(staged_path))
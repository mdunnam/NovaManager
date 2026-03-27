"""
SVG icon library for PhotoFlow.

All icons are drawn on a 20×20 coordinate space with:
  viewBox="0 0 20 20", fill="none", stroke="currentColor",
  strokeWidth="1.5", strokeLinecap="round", strokeLinejoin="round"

Usage:
    from core.icons import icon, icon_btn

    btn = QPushButton()
    btn.setIcon(icon("refresh"))
    btn.setToolTip("Refresh")
    btn.setIconSize(QSize(18, 18))

    # Or use the helper to create icon-only toolbar buttons:
    btn = icon_btn("refresh", "Refresh library", parent=self)
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QPushButton, QWidget

try:
    from PyQt6.QtSvg import QSvgRenderer
    _HAS_SVG = True
except ImportError:
    _HAS_SVG = False

# ---------------------------------------------------------------------------
# SVG template – each inner string is pasted between the <svg> tags.
# ---------------------------------------------------------------------------
_SVG_TMPL = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" '
    'fill="none" stroke="{color}" stroke-width="1.5" '
    'stroke-linecap="round" stroke-linejoin="round" '
    'width="{size}" height="{size}">{inner}</svg>'
)

# ---------------------------------------------------------------------------
# Icon definitions — name → SVG inner elements
# ---------------------------------------------------------------------------
_ICONS: dict[str, str] = {
    # ── General actions ──────────────────────────────────────────────────
    "refresh": (
        '<path d="M16 10a6 6 0 1 1-1.8-4.2"/>'
        '<polyline points="16 4 16 10 10 10"/>'
    ),
    "folder": (
        '<path d="M2 6a2 2 0 0 1 2-2h3l2 2h7a2 2 0 0 1 2 2v7'
        'a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6z"/>'
    ),
    "search": (
        '<circle cx="8.5" cy="8.5" r="5"/>'
        '<line x1="17" y1="17" x2="13" y2="13"/>'
    ),
    "search_clear": (
        '<circle cx="10" cy="10" r="8"/>'
        '<line x1="7" y1="7" x2="13" y2="13"/>'
        '<line x1="13" y1="7" x2="7" y2="13"/>'
    ),
    "save": (
        '<path d="M3 3h11.5L17 5.5V17a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V3z"/>'
        '<rect x="7" y="3" width="6" height="4"/>'
        '<rect x="6" y="11" width="8" height="6"/>'
    ),
    "trash": (
        '<polyline points="3 6 5 6 17 6"/>'
        '<path d="M6 6l1 12h6l1-12"/>'
        '<path d="M8 6V4h4v2"/>'
    ),
    "plus": (
        '<line x1="10" y1="3" x2="10" y2="17"/>'
        '<line x1="3" y1="10" x2="17" y2="10"/>'
    ),
    "close": (
        '<line x1="4" y1="4" x2="16" y2="16"/>'
        '<line x1="16" y1="4" x2="4" y2="16"/>'
    ),
    "check": '<polyline points="3 10 8 15 17 5"/>',
    "copy": (
        '<rect x="7" y="7" width="10" height="10" rx="1"/>'
        '<path d="M14 7V5a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h2"/>'
    ),
    "pencil": (
        '<path d="M14 2l4 4-10 10H4v-4L14 2z"/>'
        '<line x1="12" y1="4" x2="16" y2="8"/>'
    ),
    "link_external": (
        '<path d="M9 4H4a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h11a1 1 0 0 0 1-1v-5"/>'
        '<polyline points="13 2 18 2 18 7"/>'
        '<line x1="10" y1="10" x2="18" y2="2"/>'
    ),
    "warning": (
        '<path d="M10 2L1 17h18L10 2z"/>'
        '<line x1="10" y1="9" x2="10" y2="13"/>'
        '<line x1="10" y1="15.5" x2="10.01" y2="15.5" stroke-width="2"/>'
    ),
    "settings": (
        '<circle cx="10" cy="10" r="3"/>'
        '<path d="M10 2v1.5M10 16.5V18M2 10h1.5M16.5 10H18'
        'M4.4 4.4l1 1M14.6 14.6l1 1M4.4 15.6l1-1M14.6 5.4l1-1"/>'
    ),
    "eye": (
        '<path d="M2 10s3-6 8-6 8 6 8 6-3 6-8 6-8-6-8-6z"/>'
        '<circle cx="10" cy="10" r="2.5"/>'
    ),
    "eye_off": (
        '<line x1="3" y1="3" x2="17" y2="17"/>'
        '<path d="M8 4.5A7.5 7.5 0 0 1 18 10a12 12 0 0 1-1.8 3"/>'
        '<path d="M4.7 6.7A7.5 7.5 0 0 0 2 10s3 6 8 6a7.3 7.3 0 0 0 4.3-1.4"/>'
    ),
    "undo": (
        '<path d="M4 8H12a4 4 0 0 1 0 8H7"/>'
        '<polyline points="7 4 3 8 7 12"/>'
    ),
    "redo": (
        '<path d="M16 8H8a4 4 0 0 0 0 8h5"/>'
        '<polyline points="13 4 17 8 13 12"/>'
    ),
    "lock_closed": (
        '<rect x="4" y="9" width="12" height="9" rx="1"/>'
        '<path d="M7 9V6.5a3 3 0 1 1 6 0V9"/>'
    ),
    "lock_open": (
        '<rect x="4" y="9" width="12" height="9" rx="1"/>'
        '<path d="M7 9V6.5a3 3 0 0 1 6 0"/>'
    ),
    "list": (
        '<line x1="3" y1="5" x2="17" y2="5"/>'
        '<line x1="3" y1="10" x2="17" y2="10"/>'
        '<line x1="3" y1="15" x2="17" y2="15"/>'
    ),
    "arrow_right": (
        '<line x1="3" y1="10" x2="17" y2="10"/>'
        '<polyline points="12 5 17 10 12 15"/>'
    ),
    "retry": (
        '<path d="M19 8A9 9 0 1 0 17 14"/>'
        '<polyline points="19 2 19 8 13 8"/>'
    ),
    "stop": (
        '<circle cx="10" cy="10" r="8"/>'
        '<rect x="7" y="7" width="6" height="6" fill="currentColor" stroke="none"/>'
    ),
    "calendar": (
        '<rect x="2" y="4" width="16" height="14" rx="1"/>'
        '<line x1="2" y1="9" x2="18" y2="9"/>'
        '<line x1="6" y1="2" x2="6" y2="6"/>'
        '<line x1="14" y1="2" x2="14" y2="6"/>'
    ),
    "clock": (
        '<circle cx="10" cy="10" r="8"/>'
        '<polyline points="10 5 10 10 14 13"/>'
    ),
    "history": (
        '<circle cx="10" cy="10" r="8"/>'
        '<polyline points="10 6 10 10 14 12"/>'
        '<path d="M2 10H4" stroke-dasharray="2 2"/>'
    ),
    "backup": (
        '<path d="M16 14v2a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h9l3 3v3"/>'
        '<polyline points="10 10 10 17"/>'
        '<polyline points="7 14 10 17 13 14"/>'
    ),
    "restore": (
        '<path d="M4 8H12a4 4 0 0 1 0 8H7"/>'
        '<polyline points="7 4 3 8 7 12"/>'
    ),
    "revert": (
        '<path d="M4 8H12a4 4 0 0 1 0 8H7"/>'
        '<polyline points="7 4 3 8 7 12"/>'
    ),
    "clear_data": (
        '<path d="M3 6h14"/>'
        '<path d="M8 6V4h4v2"/>'
        '<path d="M5 6l1 12h8l1-12"/>'
        '<line x1="9" y1="10" x2="9" y2="14"/>'
        '<line x1="11" y1="10" x2="11" y2="14"/>'
    ),
    "export": (
        '<path d="M17 14v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-3"/>'
        '<polyline points="7 10 10 13 13 10"/>'
        '<line x1="10" y1="3" x2="10" y2="13"/>'
    ),
    "upload": (
        '<path d="M17 14v3a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-3"/>'
        '<polyline points="13 6 10 3 7 6"/>'
        '<line x1="10" y1="3" x2="10" y2="13"/>'
    ),
    "send": (
        '<path d="M18 2L2 9l6 2 2 7 8-16z"/>'
        '<line x1="8" y1="11" x2="13" y2="6"/>'
    ),
    "broadcast": (
        '<circle cx="10" cy="10" r="2" fill="currentColor" stroke="none"/>'
        '<path d="M6.3 6.3a5 5 0 0 0 0 7.4"/>'
        '<path d="M13.7 6.3a5 5 0 0 1 0 7.4"/>'
        '<path d="M4 4a9 9 0 0 0 0 12"/>'
        '<path d="M16 4a9 9 0 0 1 0 12"/>'
    ),
    "scan": (
        '<rect x="2" y="2" width="7" height="7" rx="1"/>'
        '<rect x="11" y="2" width="7" height="7" rx="1"/>'
        '<rect x="2" y="11" width="7" height="7" rx="1"/>'
        '<circle cx="14.5" cy="14.5" r="3.5"/>'
        '<line x1="17" y1="17" x2="19" y2="19"/>'
    ),
    "rename": (
        '<path d="M3 17h14"/>'
        '<path d="M10 5v8"/>'
        '<path d="M7 8l3-3 3 3"/>'
        '<path d="M5 3h10"/>'
    ),
    "resize_image": (
        '<polyline points="2 14 2 18 6 18"/>'
        '<polyline points="18 6 18 2 14 2"/>'
        '<line x1="2" y1="18" x2="8" y2="12"/>'
        '<line x1="18" y1="2" x2="12" y2="8"/>'
    ),
    "watermark": (
        '<path d="M10 3l2 4h4l-3.5 2.5 1.3 4L10 11.5l-3.8 2 1.3-4L4 7h4l2-4z"/>'
    ),
    "move_up": (
        '<polyline points="6 10 10 5 14 10"/>'
        '<line x1="10" y1="5" x2="10" y2="17"/>'
    ),
    "move_down": (
        '<polyline points="6 10 10 15 14 10"/>'
        '<line x1="10" y1="15" x2="10" y2="3"/>'
    ),
    "duplicate": (
        '<rect x="4" y="7" width="10" height="10" rx="1"/>'
        '<path d="M8 7V5a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-2"/>'
    ),
    "expand": (
        '<path d="M3 9V3h6"/>'
        '<path d="M3 3l7 7"/>'
        '<path d="M17 11v6h-6"/>'
        '<path d="M17 17l-7-7"/>'
    ),
    "relink": (
        '<path d="M7.5 7.5H4a3 3 0 0 0 0 6h3.5"/>'
        '<path d="M12.5 7.5H16a3 3 0 0 1 0 6h-3.5"/>'
        '<line x1="7" y1="10" x2="13" y2="10"/>'
    ),
    "notes": (
        '<path d="M14 2H4a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6L14 2z"/>'
        '<polyline points="14 2 14 6 18 6"/>'
        '<line x1="6" y1="10" x2="14" y2="10"/>'
        '<line x1="6" y1="14" x2="12" y2="14"/>'
    ),
    "export_tasks": (
        '<path d="M14 2H4a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6L14 2z"/>'
        '<polyline points="14 2 14 6 18 6"/>'
        '<polyline points="7 14 10 17 13 14"/>'
        '<line x1="10" y1="10" x2="10" y2="17"/>'
    ),

    # ── Photo / image ────────────────────────────────────────────────────
    "image": (
        '<rect x="2" y="3" width="16" height="14" rx="1"/>'
        '<circle cx="7" cy="8" r="1.5"/>'
        '<polyline points="2 14 7 9 11 12 14 9 18 13"/>'
    ),
    "tag": (
        '<path d="M3 3h7l7 7-7 7-7-7V3z"/>'
        '<circle cx="7.5" cy="7.5" r="1" fill="currentColor" stroke="none"/>'
    ),
    "package": (
        '<path d="M10 1L2 5v10l8 4 8-4V5L10 1z"/>'
        '<line x1="2" y1="5" x2="10" y2="9"/>'
        '<line x1="18" y1="5" x2="10" y2="9"/>'
        '<line x1="10" y1="9" x2="10" y2="19"/>'
    ),
    "unpackage": (
        '<path d="M10 1L2 5v10l8 4 8-4V5L10 1z"/>'
        '<line x1="2" y1="5" x2="10" y2="9"/>'
        '<line x1="18" y1="5" x2="10" y2="9"/>'
        '<line x1="10" y1="9" x2="10" y2="19"/>'
        '<line x1="7" y1="12" x2="13" y2="12"/>'
    ),
    "layers": (
        '<polyline points="2 9 10 4 18 9"/>'
        '<polyline points="2 13 10 8 18 13"/>'
        '<polyline points="2 17 10 12 18 17"/>'
    ),
    "select_all": (
        '<rect x="2" y="2" width="7" height="7" rx="1"/>'
        '<polyline points="4 5.5 5.5 7 8 4"/>'
        '<rect x="11" y="2" width="7" height="7" rx="1"/>'
        '<polyline points="13 5.5 14.5 7 17 4"/>'
        '<rect x="2" y="11" width="7" height="7" rx="1"/>'
        '<polyline points="4 14.5 5.5 16 8 13"/>'
        '<rect x="11" y="11" width="7" height="7" rx="1"/>'
        '<polyline points="13 14.5 14.5 16 17 13"/>'
    ),
    "deselect_all": (
        '<rect x="2" y="2" width="7" height="7" rx="1"/>'
        '<rect x="11" y="2" width="7" height="7" rx="1"/>'
        '<rect x="2" y="11" width="7" height="7" rx="1"/>'
        '<rect x="11" y="11" width="7" height="7" rx="1"/>'
    ),
    "thumbnail_grid": (
        '<rect x="2" y="2" width="7" height="7" rx="1"/>'
        '<rect x="11" y="2" width="7" height="7" rx="1"/>'
        '<rect x="2" y="11" width="7" height="7" rx="1"/>'
        '<rect x="11" y="11" width="7" height="7" rx="1"/>'
    ),
    "bulk_edit": (
        '<line x1="3" y1="6" x2="10" y2="6"/>'
        '<line x1="3" y1="10" x2="16" y2="10"/>'
        '<line x1="3" y1="14" x2="16" y2="14"/>'
        '<path d="M14 3l2 2.5-4.5 4H9.5v-2l4.5-4.5z"/>'
    ),
    "thumbnail_size": (
        '<rect x="2" y="4" width="10" height="10" rx="1"/>'
        '<rect x="14" y="7" width="5" height="5" rx="1"/>'
    ),
    "staged": (
        '<circle cx="10" cy="10" r="8"/>'
        '<polyline points="6 10 9 13 14 7"/>'
    ),
    "unstage": (
        '<circle cx="10" cy="10" r="8"/>'
        '<line x1="7" y1="7" x2="13" y2="13"/>'
        '<line x1="13" y1="7" x2="7" y2="13"/>'
    ),
    "status": (
        '<circle cx="10" cy="10" r="8"/>'
        '<line x1="10" y1="6" x2="10" y2="10"/>'
        '<circle cx="10" cy="13.5" r="0.8" fill="currentColor" stroke="none"/>'
    ),

    # ── Album ────────────────────────────────────────────────────────────
    "new_album": (
        '<rect x="3" y="4" width="14" height="14" rx="1"/>'
        '<path d="M7 2h6"/>'
        '<line x1="10" y1="8" x2="10" y2="14"/>'
        '<line x1="7" y1="11" x2="13" y2="11"/>'
    ),
    "smart_album": (
        '<rect x="3" y="4" width="14" height="14" rx="1"/>'
        '<path d="M7 2h6"/>'
        '<path d="M10 7l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/>'
    ),
    "add_photo": (
        '<rect x="2" y="3" width="16" height="14" rx="1"/>'
        '<line x1="10" y1="7" x2="10" y2="13"/>'
        '<line x1="7" y1="10" x2="13" y2="10"/>'
    ),
    "set_cover": (
        '<rect x="2" y="3" width="16" height="14" rx="1"/>'
        '<polyline points="2 13 6 9 9 11 12 8 16 12"/>'
        '<path d="M14 4.5l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/>'
    ),

    # ── Zoom / editor ────────────────────────────────────────────────────
    "zoom_in": (
        '<circle cx="9" cy="9" r="6"/>'
        '<line x1="17" y1="17" x2="13" y2="13"/>'
        '<line x1="9" y1="6" x2="9" y2="12"/>'
        '<line x1="6" y1="9" x2="12" y2="9"/>'
    ),
    "zoom_out": (
        '<circle cx="9" cy="9" r="6"/>'
        '<line x1="17" y1="17" x2="13" y2="13"/>'
        '<line x1="6" y1="9" x2="12" y2="9"/>'
    ),
    "zoom_fit": (
        '<polyline points="3 8 3 3 8 3"/>'
        '<polyline points="17 8 17 3 12 3"/>'
        '<polyline points="3 12 3 17 8 17"/>'
        '<polyline points="17 12 17 17 12 17"/>'
    ),
    "zoom_100": (
        '<rect x="4" y="4" width="12" height="12" rx="1"/>'
        '<line x1="4" y1="10" x2="16" y2="10"/>'
        '<line x1="10" y1="4" x2="10" y2="16"/>'
    ),
    "pen": '<path d="M15 3l2 2-10 10-3 1 1-3 10-10z"/>',
    "eraser": '<path d="M17 14l-8-8-5 5 4 4h9zm-8-8l5 5"/>',
    "text_t": (
        '<line x1="4" y1="5" x2="16" y2="5"/>'
        '<line x1="10" y1="5" x2="10" y2="17"/>'
    ),
    "circle_tool": (
        '<circle cx="10" cy="11" r="6"/>'
        '<line x1="10" y1="2" x2="10" y2="4"/>'
    ),
    "arrow_tool": (
        '<line x1="4" y1="16" x2="13" y2="7"/>'
        '<polyline points="7 7 13 7 13 13"/>'
    ),
    "color_picker": (
        '<path d="M2 10a8 8 0 1 0 16 0 8 8 0 0 0-16 0z"/>'
        '<circle cx="6.5" cy="7.5" r="1.5" fill="currentColor" stroke="none"/>'
        '<circle cx="13.5" cy="7.5" r="1.5" fill="currentColor" stroke="none"/>'
        '<circle cx="10" cy="14" r="1.5" fill="currentColor" stroke="none"/>'
    ),
    "split_view": (
        '<line x1="10" y1="2" x2="10" y2="18"/>'
        '<rect x="2" y="4" width="6" height="12" rx="1"/>'
        '<rect x="12" y="4" width="6" height="12" rx="1"/>'
    ),
    "brush": (
        '<path d="M14 3l3 3-8 8a3 3 0 0 1-4-4l9-7z"/>'
        '<path d="M6 14c0 1.5-1 3-3 4 1.5 0 3-1 4-3"/>'
    ),
    "blur_tool": (
        '<path d="M4 8 Q7 5 10 8 Q13 11 16 8"/>'
        '<path d="M4 12 Q7 9 10 12 Q13 15 16 12"/>'
        '<path d="M4 16 Q7 13 10 16 Q13 19 16 16"/>'
    ),
    "clone_stamp": (
        '<circle cx="8" cy="8" r="4"/>'
        '<line x1="12" y1="12" x2="17" y2="17"/>'
        '<line x1="15" y1="12" x2="12" y2="15"/>'
    ),
    "wand": (
        '<line x1="4" y1="16" x2="10" y2="10"/>'
        '<path d="M13 2l1 3 3 1-3 1-1 3-1-3-3-1 3-1z"/>'
    ),
    "before_after": (
        '<rect x="2" y="4" width="7" height="12" rx="1"/>'
        '<rect x="11" y="4" width="7" height="12" rx="1"/>'
        '<path d="M10 4v12" stroke-dasharray="2 2"/>'
    ),
    "center_divider": (
        '<line x1="10" y1="2" x2="10" y2="18"/>'
        '<polyline points="6 6 10 3 14 6"/>'
        '<polyline points="6 14 10 17 14 14"/>'
    ),

    # ── AI ───────────────────────────────────────────────────────────────
    "sparkle": (
        '<path d="M10 2l1.5 4 4 1.5-4 1.5L10 13l-1.5-4-4-1.5 4-1.5z"/>'
        '<path d="M17 14l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>'
    ),
    "ai_caption": (
        '<rect x="2" y="4" width="16" height="12" rx="1"/>'
        '<line x1="5" y1="8" x2="12" y2="8"/>'
        '<line x1="5" y1="12" x2="9" y2="12"/>'
        '<path d="M15 11l1 2 2 .5-2 .5-1 2-.5-2-2-.5 2-.5z"/>'
    ),
    "hashtag": (
        '<line x1="5" y1="7" x2="16" y2="7"/>'
        '<line x1="4" y1="13" x2="15" y2="13"/>'
        '<line x1="8" y1="3" x2="6" y2="17"/>'
        '<line x1="14" y1="3" x2="12" y2="17"/>'
    ),
    "reanalyze": (
        '<circle cx="10" cy="10" r="7"/>'
        '<path d="M10 6v4l3 3"/>'
        '<polyline points="15 4 17 2 19 4"/>'
    ),
    "train": (
        '<circle cx="10" cy="9" r="4"/>'
        '<path d="M7 9h6M10 6v6"/>'
        '<path d="M5 16l2-3h6l2 3"/>'
    ),
    "smart": (
        '<path d="M10 2l2 5 5 2-5 2-2 5-2-5-5-2 5-2z"/>'
        '<path d="M16 14l1 2 2 1-2 1-1 2-.5-2-2-1 2-1z"/>'
    ),
    "preset_add": (
        '<circle cx="10" cy="10" r="8"/>'
        '<line x1="10" y1="6" x2="10" y2="14"/>'
        '<line x1="6" y1="10" x2="14" y2="10"/>'
    ),
    "preset_remove": (
        '<circle cx="10" cy="10" r="8"/>'
        '<line x1="6" y1="10" x2="14" y2="10"/>'
    ),

    # ── Social platforms ─────────────────────────────────────────────────
    "instagram": (
        '<rect x="3" y="3" width="14" height="14" rx="3"/>'
        '<circle cx="10" cy="10" r="3.5"/>'
        '<circle cx="14.5" cy="5.5" r="0.8" fill="currentColor" stroke="none"/>'
    ),
    "tiktok": '<path d="M12 4v9a3 3 0 1 1-2-2.8V4h3a3 3 0 0 0 3 3"/>',
    "twitter_x": (
        '<line x1="3" y1="3" x2="17" y2="17"/>'
        '<line x1="17" y1="3" x2="3" y2="17"/>'
    ),
    "facebook": (
        '<path d="M14 2h-2a4 4 0 0 0-4 4v2H6v3h2v7h3v-7h2l.5-3H11V6a1 1 0 0 1 1-1h2V2z"/>'
    ),
    "threads": (
        '<circle cx="10" cy="10" r="4.5"/>'
        '<path d="M14.5 7C15.2 11 13 16 7 15"/>'
    ),
    "pinterest": (
        '<circle cx="10" cy="10" r="8"/>'
        '<path d="M7 6a3 3 0 0 1 3 3c0 2-1 3.5-2.5 3.5S5 11.5 5 10a5 5 0 0 1 5-5c2.8 0 5 2.2 5 5 0 3.3-2.2 6-5 6a5 5 0 0 1-3-1l1.5-5.5"/>'
    ),
    "manage_credentials": (
        '<circle cx="10" cy="8" r="4"/>'
        '<path d="M4 18v-1a6 6 0 0 1 12 0v1"/>'
        '<line x1="14" y1="5" x2="17" y2="3"/>'
        '<polyline points="16 3 17 3 17 6"/>'
    ),

    # ── Batch retouch presets ────────────────────────────────────────────
    "subtle": (
        '<circle cx="10" cy="10" r="7"/>'
        '<path d="M8 10a2 2 0 0 1 4 0"/>'
    ),
    "balanced": (
        '<circle cx="10" cy="10" r="7"/>'
        '<path d="M7 10a3 3 0 0 1 6 0"/>'
    ),
    "strong": (
        '<circle cx="10" cy="10" r="7"/>'
        '<path d="M5 10a5 5 0 0 1 10 0"/>'
    ),
    "retouch": (
        '<line x1="4" y1="16" x2="10" y2="10"/>'
        '<path d="M13 2l1 3 3 1-3 1-1 3-1-3-3-1 3-1z"/>'
        '<circle cx="6" cy="14" r="2"/>'
    ),
    "batch_retouch": (
        '<rect x="4" y="6" width="12" height="10" rx="1"/>'
        '<line x1="8" y1="3" x2="8" y2="6"/>'
        '<line x1="12" y1="3" x2="12" y2="6"/>'
        '<path d="M10 9l1 2 2 .5-2 .5-1 2-.5-2-2-.5 2-.5z"/>'
    ),
    "test_photo": (
        '<rect x="2" y="3" width="16" height="14" rx="1"/>'
        '<polyline points="10 7 10 13 7 11"/>'
    ),
    "sync": (
        '<polyline points="1 4 1 10 7 10"/>'
        '<polyline points="23 20 23 14 17 14"/>'
        '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>'
    ),
    "retouch_history": (
        '<circle cx="10" cy="10" r="8"/>'
        '<polyline points="10 6 10 10 13 13"/>'
        '<path d="M3 10H5" stroke-dasharray="2 2"/>'
    ),

    # ── Missing / alias icons ─────────────────────────────────────────────
    "pen_draw": (
        '<path d="M15 3l2 2-10 10-3 1 1-3 10-10z"/>'
        '<line x1="2" y1="18" x2="6" y2="18"/>'
    ),
    "cursor_select": (
        '<path d="M4 4l5 12 2.5-4.5 4.5-2.5L4 4z"/>'
        '<line x1="11.5" y1="11.5" x2="17" y2="17"/>'
    ),
    "shape_circle": (
        '<circle cx="10" cy="10" r="7"/>'
    ),
    "text_tool": (
        '<line x1="4" y1="5" x2="16" y2="5"/>'
        '<line x1="10" y1="5" x2="10" y2="17"/>'
        '<line x1="7" y1="17" x2="13" y2="17"/>'
    ),
    "compare_split": (
        '<line x1="10" y1="2" x2="10" y2="18" stroke-dasharray="3 2"/>'
        '<rect x="2" y="4" width="6" height="12" rx="1"/>'
        '<rect x="12" y="4" width="6" height="12" rx="1"/>'
    ),
    "arrow_left": (
        '<line x1="17" y1="10" x2="3" y2="10"/>'
        '<polyline points="8 5 3 10 8 15"/>'
    ),
    "arrow_up": (
        '<line x1="10" y1="17" x2="10" y2="3"/>'
        '<polyline points="5 8 10 3 15 8"/>'
    ),
    "arrow_down": (
        '<line x1="10" y1="3" x2="10" y2="17"/>'
        '<polyline points="5 12 10 17 15 12"/>'
    ),
    "lock": (
        '<rect x="4" y="9" width="12" height="9" rx="1"/>'
        '<path d="M7 9V6.5a3 3 0 1 1 6 0V9"/>'
    ),
    "flag": (
        '<path d="M4 2v16"/>'
        '<path d="M4 4h10l-2 4 2 4H4"/>'
    ),
}


def _make_svg(name: str, size: int, color: str) -> str:
    """Build a complete SVG string for the given icon name."""
    inner = _ICONS.get(name, _ICONS["close"])
    return _SVG_TMPL.format(inner=inner, size=size, color=color)


def icon(
    name: str,
    size: int = 18,
    color: str = "#cccccc",
) -> QIcon:
    """
    Return a QIcon for the named SVG icon.

    Args:
        name:  Key from the _ICONS dictionary (e.g. "refresh", "trash").
        size:  Pixel size of the rendered icon (default 18).
        color: CSS colour string used as stroke colour (default "#cccccc").

    Returns:
        A QIcon filled with the rendered SVG, or a blank QIcon if
        PyQt6.QtSvg is unavailable.
    """
    if not _HAS_SVG:
        return QIcon()

    svg_bytes = QByteArray(_make_svg(name, size, color).encode("utf-8"))
    renderer = QSvgRenderer(svg_bytes)

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def icon_btn(
    icon_name: str,
    tooltip: str,
    *,
    size: int = 18,
    color: str = "#cccccc",
    checkable: bool = False,
    fixed_size: Optional[tuple[int, int]] = None,
    parent: Optional[QWidget] = None,
) -> QPushButton:
    """
    Create an icon-only QPushButton with a tooltip.

    Args:
        icon_name:  Key from the _ICONS dictionary.
        tooltip:    Tooltip text shown on hover (required for accessibility).
        size:       Icon pixel size (default 18).
        color:      Stroke colour for the SVG (default "#cccccc").
        checkable:  If True, the button is checkable.
        fixed_size: Optional (width, height) tuple to fix the button size.
        parent:     Optional parent widget.

    Returns:
        A QPushButton with the icon set and no visible text label.
    """
    btn = QPushButton(parent)
    btn.setIcon(icon(icon_name, size, color))
    btn.setIconSize(QSize(size, size))
    btn.setToolTip(tooltip)
    btn.setCheckable(checkable)
    if fixed_size:
        btn.setFixedSize(*fixed_size)
    return btn

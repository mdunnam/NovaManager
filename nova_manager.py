
"""
PhotoFlow - Main Application
A desktop application for organizing photos and publishing to social media
"""
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLineEdit, QLabel, 
                             QFileDialog, QCheckBox, QTableWidget, QTableWidgetItem,
                             QProgressBar, QMessageBox, QTabWidget, QTextEdit,
                             QComboBox, QHeaderView, QAbstractItemView, QInputDialog,
                             QStyledItemDelegate, QProgressDialog, QScrollArea, QGridLayout,
                             QFrame, QSplitter, QListWidget, QToolButton, QStyle,
                             QDialog, QDialogButtonBox, QGroupBox, QSpinBox, QSlider,
                             QListWidgetItem, QColorDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QSize, QEvent, QTimer, QRect, QPointF
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QColor, QFont, QImage, QPen, QShortcut, QKeySequence, QPolygonF, QFontMetrics, QTabletEvent
from core.icons import icon as _icon
from pathlib import Path
import os
import math
import time
import hashlib
import shutil
import json
import base64
import traceback
import threading
from datetime import datetime
try:
    import numpy as np
    import cv2
except Exception:
    np = None
    cv2 = None

try:
    import ollama
except Exception:
    ollama = None

try:
    import requests
except Exception:
    requests = None

from ui.gallery_tab import GalleryTab
from ui.photos_tab import PhotosTab
from ui.publish_tab import PublishTab
from ui.filters_tab import FiltersTab
from ui.instagram_tab import InstagramTab
from ui.tiktok_tab import TikTokTab
from ui.albums_tab import AlbumsTab
from ui.composer_tab import ComposerTab
from ui.schedule_tab import ScheduleTab
from ui.settings_tab import SettingsTab
from ui.duplicates_tab import DuplicatesTab
from ui.batch_tab import BatchTab
from ui.history_tab import HistoryTab
from ui.learning_tab import AILearningTab
from ui.vocabularies_tab import VocabulariesTab
from ui.face_matching_tab import FaceMatchingTab

from core.database import PhotoDatabase
from core.ai_analyzer import analyze_image
from core.image_retoucher import ImageRetoucher


class PhotoPickerDialog(QDialog):
    """Dialog for selecting a photo from the library in a gallery view"""
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Photo")
        self.setGeometry(200, 200, 1000, 700)
        self.db = db
        self.selected_photo = None
        self.init_ui()
    
    def apply_scale(self):
        if self.base_pixmap.isNull():
            return
        clamped = max(0.1, min(self.scale_factor, 6.0))
        self.scale_factor = clamped
        scaled = self.base_pixmap.scaled(
            self.base_pixmap.size() * self.scale_factor,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.label.setPixmap(scaled)

    def set_zoom(self, factor: float):
        self.scale_factor = factor
        self.apply_scale()

    def adjust_zoom(self, delta_factor: float):
        self.scale_factor *= delta_factor
        self.apply_scale()

    def fit_to_view(self):
        if self.base_pixmap.isNull():
            return
        vp = self.scroll.viewport().size()
        if vp.width() <= 0 or vp.height() <= 0:
            return
        bw, bh = self.base_pixmap.width(), self.base_pixmap.height()
        if bw == 0 or bh == 0:
            return
        fit_scale = min(vp.width() / bw, vp.height() / bh) * 0.98
        self.set_zoom(fit_scale)

    def wheelEvent(self, event):
        # Zoom with mouse wheel; consume event to prevent scrollbar scrolling
        if event.angleDelta().y() > 0:
            self.adjust_zoom(1.1)
        else:
            self.adjust_zoom(0.9)
        event.accept()

    def on_notes_text_changed(self):
        """Auto-save notes with a small delay to avoid excessive DB writes."""
        if self.auto_save_timer is None:
            self.auto_save_timer = QTimer()
            self.auto_save_timer.setSingleShot(True)
            self.auto_save_timer.timeout.connect(self.save_notes)
        self.auto_save_timer.stop()
        self.auto_save_timer.start(1000)  # Auto-save 1 second after typing stops

    def save_notes(self):
        """Persist notes for this photo in the database and refresh parent table."""
        try:
            text = self.notes_edit.toPlainText()
            self.db.update_photo_metadata(self.photo_id, {'notes': text})
            # Refresh the parent window's Library table to show updated notes
            if self.parent() and hasattr(self.parent(), 'refresh_photo_row'):
                self.parent().refresh_photo_row(self.photo_id)
            if self.parent() and hasattr(self.parent(), 'statusBar') and self.parent().statusBar():
                self.parent().statusBar().showMessage("Notes saved", 1000)
        except Exception as e:
            print(f"save_notes error: {e}")

    def _on_label_press(self, event):
        """Start pan on middle-click."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = True
            self.pan_start_pos = event.globalPosition().toPoint()
            self.scroll_start = (self.scroll.horizontalScrollBar().value(),
                                 self.scroll.verticalScrollBar().value())
            event.accept()
        else:
            event.ignore()

    def _on_label_move(self, event):
        """Pan during middle-click drag."""
        if self.panning and self.pan_start_pos:
            delta = event.globalPosition().toPoint() - self.pan_start_pos
            h_bar = self.scroll.horizontalScrollBar()
            v_bar = self.scroll.verticalScrollBar()
            h_bar.setValue(self.scroll_start[0] - delta.x())
            v_bar.setValue(self.scroll_start[1] - delta.y())
            event.accept()
        else:
            event.ignore()

    def _on_label_release(self, event):
        """End pan on middle-click release."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = False
            self.pan_start_pos = None
            event.accept()
        else:
            event.ignore()
    


class PackageManagerDialog(QDialog):
    """Dialog to manage multiple packages with chip-like UI"""
    def __init__(self, parent=None, initial_packages=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Packages")
        self.packages = list(initial_packages or [])
        self.resize(420, 280)

        root = QVBoxLayout(self)
        info = QLabel("Add or remove packages. These apply to the selected photos.")
        info.setWordWrap(True)
        root.addWidget(info)

        # Chips area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(6, 6, 6, 6)
        self.grid.setSpacing(6)
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll)

        # Add input
        add_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a package and press Add (comma to add multiple)")
        add_btn = QPushButton("Add")
        add_btn.setIcon(_icon('preset_add'))
        add_btn.setIconSize(QSize(16, 16))
        add_btn.clicked.connect(self.on_add_clicked)
        add_row.addWidget(self.input)
        add_row.addWidget(add_btn)
        root.addLayout(add_row)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.render_chips()

    @staticmethod
    def sanitize(name: str) -> str:
        return ''.join(ch for ch in (name or '').strip() if ch.isalnum() or ch in (' ', '-', '_')).strip()

    def on_add_clicked(self):
        text = self.input.text()
        if not text:
            return
        parts = [self.sanitize(p) for p in text.split(',')]
        parts = [p for p in parts if p]
        added = False
        for p in parts:
            if p not in self.packages:
                self.packages.append(p)
                added = True
        if added:
            self.render_chips()
        self.input.clear()

    def remove_pkg(self, pkg: str):
        self.packages = [p for p in self.packages if p != pkg]
        self.render_chips()

    def render_chips(self):
        # Clear
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        cols = 3
        for idx, pkg in enumerate(self.packages):
            r, c = divmod(idx, cols)
            frame = QFrame()
            frame.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Raised)
            h = QHBoxLayout(frame)
            h.setContentsMargins(6, 4, 6, 4)
            label = QLabel(pkg)
            remove = QToolButton()
            try:
                remove.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
            except Exception:
                remove.setText('X')
            remove.setToolTip("Remove")
            remove.clicked.connect(lambda _=False, p=pkg: self.remove_pkg(p))
            h.addWidget(label)
            h.addStretch(1)
            h.addWidget(remove)
            self.grid.addWidget(frame, r, c)

    def get_packages(self):
        return list(self.packages)


class AnnotatedImageCanvas(QWidget):
    """Custom canvas that supports pan, zoom, and freehand annotations."""

    zoom_changed = pyqtSignal(float)
    layer_state_changed = pyqtSignal()

    LAYER_ORDER = ["Layer 1"]
    LAYER_COLORS = {
        "blemish": QColor(255, 60, 60, 210),
        "lighting": QColor(255, 204, 0, 210),
        "retouch": QColor(0, 200, 255, 210),
    }

    def __init__(self, image_path, annotation_dir, photo_id, parent=None):
        super().__init__(parent)
        self.base_pixmap = QPixmap(image_path)
        self.annotation_dir = annotation_dir
        self.photo_id = photo_id
        self.annotation_layers = {}
        self.layer_order = list(self.LAYER_ORDER)
        self.layer_settings = {
            name: {"visible": True, "opacity": 100, "blend": "normal", "lighting_prompt": "", "locked": False}
            for name in self.layer_order
        }

        self.scale_factor = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0

        self.panning = False
        self.last_pan_pos = None

        self.drawing_enabled = False
        self.drawing = False
        self.last_draw_point = None
        self._paint_debounce_timer = QTimer()
        self._paint_debounce_timer.setSingleShot(True)
        self._paint_debounce_timer.timeout.connect(self.update)
        self.show_hardness_ring = True
        self.active_layer = self.layer_order[0] if self.layer_order else "Layer 1"
        self.tool_mode = "pen"  # pen|eraser|circle|arrow|text|blemish_brush|blur_brush|clone_stamp
        self.pen_width = 5
        self.brush_hardness = 65
        self.brush_opacity = 100
        self.brush_flow = 100
        self.brush_mode = "normal"
        self.tablet_enabled = True
        self.tablet_pressure_curve = 1.35
        self.tablet_tilt_enabled = True
        self.tablet_eraser_detection = True
        self._tablet_in_proximity = False
        self._tablet_pressure = 1.0
        self._tablet_pressure_filtered = 1.0
        self._tablet_tilt_x = 0.0
        self._tablet_tilt_y = 0.0
        self._tablet_eraser_active = False
        self.markup_color = QColor(255, 60, 60, 210)
        self.clone_source_point = None
        self.clone_anchor_start = None
        self.cursor_image_point = None
        self.show_annotations = True
        self.space_pan_enabled = False
        self.shape_start = None
        self.shape_end = None
        self.compare_enabled = False
        self.compare_pixmap = None
        self.compare_ratio = 0.5
        self.compare_mode = "split"  # split|before|after
        self.compare_dragging = False
        self.text_provider = None
        self._undo_stack = []
        self._max_undo = 6
        # Full-image undo snapshots are memory-heavy on large photos.
        # Keep a safety cap to avoid crashes/OOM when starting a stroke.
        self._max_undo_pixels = 8_000_000
        self.vector_annotations = []
        self.selected_annotation_idx = None
        self._drag_mode = None  # move|resize_start|resize_end|resize_circle
        self._drag_start_point = None
        self._drag_original_annotation = None

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self.save_annotations)

        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TabletTracking, True)
        self.setMinimumSize(600, 450)
        self._init_annotation_layer()

    def set_text_provider(self, provider):
        self.text_provider = provider

    def _layer_path(self, layer_name):
        return self.annotation_dir / f"{self.photo_id:06d}_{layer_name}.png"

    def _vector_path(self):
        return self.annotation_dir / f"{self.photo_id:06d}_vector_annotations.json"

    def _layer_settings_path(self):
        return self.annotation_dir / f"{self.photo_id:06d}_layer_settings.json"

    def _composition_mode_for_layer(self, layer_name):
        blend = str(self.layer_settings.get(layer_name, {}).get("blend", "normal")).lower()
        mapping = {
            "normal": QPainter.CompositionMode.CompositionMode_SourceOver,
            "multiply": QPainter.CompositionMode.CompositionMode_Multiply,
            "screen": QPainter.CompositionMode.CompositionMode_Screen,
            "overlay": QPainter.CompositionMode.CompositionMode_Overlay,
        }
        return mapping.get(blend, QPainter.CompositionMode.CompositionMode_SourceOver)

    def _active_layer_image(self):
        return self.annotation_layers.get(self.active_layer)

    def _init_annotation_layer(self):
        if self.base_pixmap.isNull():
            return

        image_size = self.base_pixmap.size()
        for layer_name in self.layer_order:
            layer_img = QImage(image_size, QImage.Format.Format_ARGB32_Premultiplied)
            layer_img.fill(Qt.GlobalColor.transparent)
            layer_path = self._layer_path(layer_name)
            if layer_path.exists():
                loaded = QImage(str(layer_path))
                if not loaded.isNull() and loaded.size() == image_size:
                    painter = QPainter(layer_img)
                    painter.drawImage(0, 0, loaded)
                    painter.end()
            self.annotation_layers[layer_name] = layer_img

        if self.active_layer not in self.annotation_layers and self.layer_order:
            self.active_layer = self.layer_order[0]

        settings_path = self._layer_settings_path()
        if settings_path.exists():
            try:
                payload = json.loads(settings_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    saved_order = payload.get("order")
                    if isinstance(saved_order, list):
                        clean = [str(x) for x in saved_order if str(x) in self.annotation_layers]
                        for name in self.layer_order:
                            if name not in clean:
                                clean.append(name)
                        self.layer_order = clean
                    saved_settings = payload.get("settings")
                    if isinstance(saved_settings, dict):
                        for name in self.layer_order:
                            current = self.layer_settings.get(name, {"visible": True, "opacity": 100, "blend": "normal", "lighting_prompt": "", "locked": False})
                            src = saved_settings.get(name, {}) if isinstance(saved_settings.get(name), dict) else {}
                            current["visible"] = bool(src.get("visible", current.get("visible", True)))
                            current["opacity"] = max(0, min(100, int(src.get("opacity", current.get("opacity", 100)))))
                            current["blend"] = str(src.get("blend", current.get("blend", "normal"))).lower()
                            current["lighting_prompt"] = str(src.get("lighting_prompt", current.get("lighting_prompt", "")) or "")
                            current["locked"] = bool(src.get("locked", current.get("locked", False)))
                            self.layer_settings[name] = current
            except Exception as e:
                print(f"layer settings load error: {e}")

        vector_path = self._vector_path()
        if vector_path.exists():
            try:
                data = json.loads(vector_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.vector_annotations = data
            except Exception as e:
                print(f"vector annotation load error: {e}")

    def _schedule_autosave(self):
        self._autosave_timer.stop()
        self._autosave_timer.start(600)

    def set_active_layer(self, layer_name):
        if layer_name in self.annotation_layers:
            self.active_layer = layer_name

    def get_layer_state(self, layer_name):
        return dict(self.layer_settings.get(layer_name, {"visible": True, "opacity": 100, "blend": "normal", "lighting_prompt": "", "locked": False}))

    def set_layer_visible(self, layer_name, visible):
        if layer_name not in self.layer_settings:
            return
        self.layer_settings[layer_name]["visible"] = bool(visible)
        self.update()
        self.layer_state_changed.emit()

    def set_layer_opacity(self, layer_name, opacity):
        if layer_name not in self.layer_settings:
            return
        self.layer_settings[layer_name]["opacity"] = max(0, min(100, int(opacity)))
        self.update()
        self.layer_state_changed.emit()

    def set_layer_blend_mode(self, layer_name, blend_mode):
        if layer_name not in self.layer_settings:
            return
        self.layer_settings[layer_name]["blend"] = str(blend_mode).lower()
        self.update()
        self.layer_state_changed.emit()

    def is_layer_locked(self, layer_name):
        return bool(self.layer_settings.get(layer_name, {}).get("locked", False))

    def set_layer_locked(self, layer_name, locked):
        if layer_name not in self.layer_settings:
            return
        self.layer_settings[layer_name]["locked"] = bool(locked)
        self.layer_state_changed.emit()

    def get_layer_lighting_prompt(self, layer_name):
        if layer_name not in self.layer_settings:
            return ""
        return str(self.layer_settings[layer_name].get("lighting_prompt", ""))

    def set_layer_lighting_prompt(self, layer_name, prompt):
        if layer_name not in self.layer_settings:
            return
        self.layer_settings[layer_name]["lighting_prompt"] = str(prompt or "")
        self.layer_state_changed.emit()

    def apply_lighting_prompt(self, layer_name, prompt):
        """Apply true AI relighting to a layer using an image-edit backend."""
        if layer_name not in self.annotation_layers:
            return False, "Layer not found"
        if cv2 is None or np is None or self.base_pixmap.isNull():
            return False, "OpenCV/Numpy not available"

        text = str(prompt or "").strip()
        self.set_layer_lighting_prompt(layer_name, text)

        layer = self.annotation_layers[layer_name]
        if text == "":
            layer.fill(Qt.GlobalColor.transparent)
            self.update()
            self.layer_state_changed.emit()
            self.save_annotations()
            return True, "Lighting prompt cleared"

        src = self._compose_current_bgr()
        if src is None:
            return False, "Could not compose source image"
        out, err = self.compute_relight_image(src, text, backend="openai")
        if out is None:
            return False, err

        return self.apply_lighting_result(layer_name, text, out)

    def get_composed_image_bgr(self):
        return self._compose_current_bgr()

    def _base_image_bgr(self):
        if self.base_pixmap.isNull() or np is None:
            return None
        img = self.base_pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        ptr = img.bits()
        ptr.setsize(img.width() * img.height() * 4)
        rgba = np.frombuffer(ptr, np.uint8).reshape((img.height(), img.width(), 4)).copy()
        return cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)

    def compute_relight_image(self, source_bgr, prompt_text, backend="openai"):
        mode = str(backend or "openai").lower()
        if mode == "local":
            try:
                return self._local_relight_fallback(source_bgr, prompt_text), None
            except Exception as e:
                return None, f"Local relight failed: {e}"
        return self._ai_relight_openai(source_bgr, prompt_text)

    def apply_lighting_result(self, layer_name, prompt_text, relit_bgr):
        if layer_name not in self.annotation_layers:
            return False, "Layer not found"
        if relit_bgr is None:
            return False, "No relight result image"

        text = str(prompt_text or "").strip()
        self.set_layer_lighting_prompt(layer_name, text)

        # Always relight from the original photo to avoid feedback from existing overlays.
        source = self._base_image_bgr()
        if source is None:
            source = self._compose_current_bgr()
        if source is None:
            return False, "Could not compose source image"

        out = self._transfer_lighting_only(source, relit_bgr)

        rgba = cv2.cvtColor(out, cv2.COLOR_BGR2RGBA)
        rgba[:, :, 3] = 255
        qimg = QImage(rgba.data, rgba.shape[1], rgba.shape[0], rgba.strides[0], QImage.Format.Format_RGBA8888).copy()
        self.annotation_layers[layer_name] = qimg.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)

        # Prompt looks are usually full-frame; keep visible and default to normal blend.
        self.layer_settings[layer_name]["visible"] = True
        self.layer_settings[layer_name]["blend"] = "normal"
        self.layer_settings[layer_name]["opacity"] = 100

        self.update()
        self.layer_state_changed.emit()
        self.save_annotations()
        return True, "Lighting applied"

    def _ai_relight_openai(self, source_bgr, prompt_text):
        if requests is None:
            return None, "Real AI relighting needs 'requests' installed."

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return None, "Set OPENAI_API_KEY to use real AI relighting."

        try:
            ok, encoded = cv2.imencode(".png", source_bgr)
            if not ok:
                return None, "Could not encode source image for relighting"

            h, w = source_bgr.shape[:2]
            aspect = float(w) / float(max(1, h))
            if aspect > 1.15:
                out_size = "1536x1024"
            elif aspect < 0.87:
                out_size = "1024x1536"
            else:
                out_size = "1024x1024"

            primary_prompt = (
                "Relight this exact photo realistically. Keep the same person, pose, framing, identity, and clothing. "
                "Only change lighting, shadows, highlights, and mood as requested. "
                "Do not stylize. Keep skin texture and photo realism. "
                "Avoid style transfer/cartoon effects. Request: " + prompt_text
            )
            safe_retry_prompt = (
                "Apply neutral, PG-13 portrait relighting only. Focus on environment and light direction. "
                "Preserve the subject exactly, no body modifications, no sensual emphasis, no stylization. "
                "Request: " + prompt_text
            )

            def _post_edit(req_prompt):
                return requests.post(
                    "https://api.openai.com/v1/images/edits",
                    headers={"Authorization": f"Bearer {api_key}"},
                    data={"model": "gpt-image-1", "prompt": req_prompt, "size": out_size},
                    files={"image": ("input.png", encoded.tobytes(), "image/png")},
                    timeout=180,
                )

            response = _post_edit(primary_prompt)
            if response.status_code >= 300:
                body = response.text or ""
                is_safety_block = (response.status_code == 400 and "rejected by the safety system" in body.lower())
                if is_safety_block:
                    retry = _post_edit(safe_retry_prompt)
                    if retry.status_code < 300:
                        response = retry
                    else:
                        req_id = ""
                        try:
                            j = retry.json()
                            req_id = str(j.get("error", {}).get("request_id", "") or "")
                        except Exception:
                            pass
                        tail = f" (request_id: {req_id})" if req_id else ""
                        return None, f"AI relight was blocked by safety filters{tail}. Try a milder prompt like 'soft evening portrait lighting'."
                else:
                    return None, f"AI relight failed: {response.status_code} {body[:220]}"

            data = response.json()
            items = data.get("data", []) if isinstance(data, dict) else []
            if not items:
                return None, "AI relight returned no image"

            item0 = items[0] if isinstance(items[0], dict) else {}
            if item0.get("b64_json"):
                raw = base64.b64decode(item0.get("b64_json"))
            elif item0.get("url"):
                img_resp = requests.get(item0.get("url"), timeout=120)
                if img_resp.status_code >= 300:
                    return None, "Could not download relit image result"
                raw = img_resp.content
            else:
                return None, "AI relight response missing image payload"

            arr = np.frombuffer(raw, dtype=np.uint8)
            relit = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if relit is None:
                return None, "Could not decode relit image"

            h, w = source_bgr.shape[:2]
            if relit.shape[0] != h or relit.shape[1] != w:
                relit = cv2.resize(relit, (w, h), interpolation=cv2.INTER_LANCZOS4)

            # If API returns almost the same image, fall back to stronger local relight.
            mad = float(np.mean(np.abs(relit.astype(np.float32) - source_bgr.astype(np.float32))))
            if mad < 2.0:
                relit = self._local_relight_fallback(source_bgr, prompt_text)

            return relit, None
        except Exception as e:
            return None, f"AI relight exception: {e}"

    def _local_relight_fallback(self, source_bgr, prompt_text):
        p = str(prompt_text or "").lower()
        out = source_bgr.astype(np.float32)
        h, w = out.shape[:2]
        changed = False

        if "night" in p:
            out[:, :, 0] *= 1.08
            out[:, :, 1] *= 0.74
            out[:, :, 2] *= 0.64
            changed = True
        if "studio" in p or "soft" in p:
            out *= 1.08
            changed = True
        if "dramatic" in p:
            out = (out - 127.5) * 1.2 + 127.5
            changed = True
        if "spot" in p or "flash" in p:
            yy, xx = np.ogrid[:h, :w]
            cx, cy = w * 0.5, h * 0.45
            rx = (xx - cx) / max(1.0, w * 0.32)
            ry = (yy - cy) / max(1.0, h * 0.32)
            radial = np.exp(-(rx * rx + ry * ry) * 2.0)
            out *= (0.68 + 0.52 * radial[:, :, None])
            changed = True

        # Ensure generic prompts still apply a visible relight delta.
        if not changed:
            out = (out - 127.5) * 1.12 + 127.5
            out *= 0.96

        return np.clip(out, 0, 255).astype(np.uint8)

    def _transfer_lighting_only(self, source_bgr, relit_bgr):
        """Keep original structure/colors and borrow only luminance from AI relight output."""
        src_lab = cv2.cvtColor(source_bgr, cv2.COLOR_BGR2LAB)
        rel_lab = cv2.cvtColor(relit_bgr, cv2.COLOR_BGR2LAB)

        src_l = src_lab[:, :, 0].astype(np.float32)
        rel_l = rel_lab[:, :, 0].astype(np.float32)

        # Smooth target luminance so lighting changes are natural and avoid texture warping artifacts.
        rel_l = cv2.bilateralFilter(rel_l.astype(np.uint8), 7, 35, 35).astype(np.float32)

        # Transfer only luminance; keep source chroma (A/B) to preserve identity and scene structure.
        out_lab = src_lab.copy()
        delta = rel_l - src_l
        strength = 1.35
        out_l = src_l + delta * strength
        out_lab[:, :, 0] = np.clip(out_l, 0, 255).astype(np.uint8)
        return cv2.cvtColor(out_lab, cv2.COLOR_LAB2BGR)

    def move_active_layer(self, direction):
        if self.active_layer not in self.layer_order:
            return
        idx = self.layer_order.index(self.active_layer)
        new_idx = idx + int(direction)
        if new_idx < 0 or new_idx >= len(self.layer_order):
            return
        self.layer_order[idx], self.layer_order[new_idx] = self.layer_order[new_idx], self.layer_order[idx]
        self.update()
        self.layer_state_changed.emit()

    def set_tool_mode(self, mode):
        self.tool_mode = mode

    def set_space_pan_enabled(self, enabled):
        self.space_pan_enabled = bool(enabled)

    def set_compare_enabled(self, enabled):
        self.compare_enabled = bool(enabled)
        self.update()

    def set_compare_mode(self, mode):
        if mode in ("split", "before", "after"):
            self.compare_mode = mode
            self.update()

    def set_compare_pixmap(self, pixmap):
        self.compare_pixmap = pixmap
        self.update()

    def set_compare_ratio(self, ratio):
        self.compare_ratio = max(0.05, min(0.95, float(ratio)))
        self.update()

    def current_layer_color(self):
        return QColor(self.markup_color)

    def set_markup_color(self, color):
        if isinstance(color, QColor) and color.isValid():
            self.markup_color = QColor(color)

    def set_brush_hardness(self, value):
        self.brush_hardness = max(1, min(100, int(value)))

    def set_brush_opacity(self, value):
        self.brush_opacity = max(1, min(100, int(value)))

    def set_brush_flow(self, value):
        self.brush_flow = max(1, min(100, int(value)))

    def set_brush_mode(self, mode):
        self.brush_mode = str(mode or "normal").lower()

    def set_tablet_enabled(self, enabled):
        self.tablet_enabled = bool(enabled)

    def set_tablet_pressure_curve(self, value):
        # UI uses 10..200 where 100 = linear.
        iv = max(10, min(200, int(value)))
        self.tablet_pressure_curve = float(iv) / 100.0

    def set_tablet_tilt_enabled(self, enabled):
        self.tablet_tilt_enabled = bool(enabled)

    def set_tablet_eraser_detection(self, enabled):
        self.tablet_eraser_detection = bool(enabled)

    def _effective_brush_params(self):
        width = float(self.pen_width)
        hardness = float(self.brush_hardness)
        opacity = float(self.brush_opacity)
        flow = float(self.brush_flow)

        if self.tablet_enabled and self._tablet_in_proximity:
            p = max(0.0, min(1.0, float(self._tablet_pressure_filtered)))
            # Pressure curve >1 gives more fine control at low pressure.
            p_curve = p ** max(0.1, float(self.tablet_pressure_curve))
            width = max(1.0, width * (0.16 + 1.24 * p_curve))
            opacity = max(1.0, min(100.0, opacity * (0.12 + 0.88 * p_curve)))
            flow = max(1.0, min(100.0, flow * (0.10 + 0.90 * p_curve)))

            if self.tablet_tilt_enabled:
                tx = max(-60.0, min(60.0, float(self._tablet_tilt_x)))
                ty = max(-60.0, min(60.0, float(self._tablet_tilt_y)))
                tilt_mag = min(1.0, ((tx * tx + ty * ty) ** 0.5) / 60.0)
                width *= (1.0 + 0.35 * tilt_mag)
                hardness *= (1.0 - 0.35 * tilt_mag)

        return {
            "width": max(1, int(round(width))),
            "hardness": max(1, min(100, int(round(hardness)))),
            "opacity": max(1, min(100, int(round(opacity)))),
            "flow": max(1, min(100, int(round(flow)))),
        }

    def add_layer(self, layer_name):
        name = str(layer_name or "").strip()
        if not name or name in self.annotation_layers:
            return False
        if self.base_pixmap.isNull():
            return False
        layer_img = QImage(self.base_pixmap.size(), QImage.Format.Format_ARGB32_Premultiplied)
        layer_img.fill(Qt.GlobalColor.transparent)
        self.annotation_layers[name] = layer_img
        self.layer_order.append(name)
        self.layer_settings[name] = {"visible": True, "opacity": 100, "blend": "normal", "lighting_prompt": "", "locked": False}
        self.active_layer = name
        self.layer_state_changed.emit()
        self.update()
        self.save_annotations()
        return True

    def duplicate_layer(self, source_name, new_name):
        src = str(source_name or "").strip()
        dst = str(new_name or "").strip()
        if not src or not dst or src == dst:
            return False
        if src not in self.annotation_layers or dst in self.annotation_layers:
            return False
        src_img = self.annotation_layers.get(src)
        if src_img is None or src_img.isNull():
            return False
        self.annotation_layers[dst] = src_img.copy()
        src_settings = dict(self.layer_settings.get(src, {}))
        src_settings["locked"] = False
        self.layer_settings[dst] = src_settings
        src_index = self.layer_order.index(src)
        self.layer_order.insert(src_index + 1, dst)
        self.active_layer = dst
        self.layer_state_changed.emit()
        self.update()
        self.save_annotations()
        return True

    def rename_layer(self, old_name, new_name):
        src = str(old_name or "").strip()
        dst = str(new_name or "").strip()
        if not src or not dst or src == dst:
            return False
        if src not in self.annotation_layers or dst in self.annotation_layers:
            return False
        self.annotation_layers[dst] = self.annotation_layers.pop(src)
        self.layer_settings[dst] = self.layer_settings.pop(src)
        self.layer_order = [dst if n == src else n for n in self.layer_order]
        for ann in self.vector_annotations:
            if ann.get("layer") == src:
                ann["layer"] = dst
        if self.active_layer == src:
            self.active_layer = dst
        try:
            old_path = self._layer_path(src)
            new_path = self._layer_path(dst)
            if old_path.exists():
                old_path.rename(new_path)
        except Exception:
            pass
        self.layer_state_changed.emit()
        self.update()
        self.save_annotations()
        return True

    def delete_layer(self, layer_name):
        name = str(layer_name or "").strip()
        if name not in self.annotation_layers:
            return False
        if len(self.layer_order) <= 1:
            return False
        del self.annotation_layers[name]
        self.layer_settings.pop(name, None)
        self.layer_order = [n for n in self.layer_order if n != name]
        self.vector_annotations = [a for a in self.vector_annotations if a.get("layer") != name]
        if self.active_layer == name:
            self.active_layer = self.layer_order[0]
        try:
            p = self._layer_path(name)
            if p.exists():
                p.unlink()
        except Exception:
            pass
        self.layer_state_changed.emit()
        self.update()
        self.save_annotations()
        return True

    def fit_to_view(self):
        if self.base_pixmap.isNull():
            return

        vw = max(1, self.width())
        vh = max(1, self.height())
        bw = self.base_pixmap.width()
        bh = self.base_pixmap.height()
        if bw <= 0 or bh <= 0:
            return

        self.scale_factor = min(vw / bw, vh / bh) * 0.98
        self.offset_x = (vw - bw * self.scale_factor) / 2.0
        self.offset_y = (vh - bh * self.scale_factor) / 2.0
        self.zoom_changed.emit(self.scale_factor)
        self.update()

    def set_zoom(self, factor, anchor=None):
        if self.base_pixmap.isNull():
            return

        new_scale = max(0.05, min(6.0, factor))
        old_scale = self.scale_factor
        if old_scale <= 0:
            old_scale = 1.0

        if anchor is not None:
            ax = float(anchor.x())
            ay = float(anchor.y())
            image_x = (ax - self.offset_x) / old_scale
            image_y = (ay - self.offset_y) / old_scale
            self.offset_x = ax - image_x * new_scale
            self.offset_y = ay - image_y * new_scale

        self.scale_factor = new_scale
        self.zoom_changed.emit(self.scale_factor)
        self.update()

    def adjust_zoom(self, factor, anchor=None):
        self.set_zoom(self.scale_factor * factor, anchor)

    def set_pen_width(self, width):
        self.pen_width = max(1, int(width))

    def set_drawing_enabled(self, enabled):
        self.drawing_enabled = bool(enabled)
        self.drawing = False
        self.last_draw_point = None

    def set_show_annotations(self, show):
        self.show_annotations = bool(show)
        self.update()

    def _push_undo_snapshot(self):
        layer = self._active_layer_image()
        if layer is None or layer.isNull():
            return
        if layer.width() * layer.height() > self._max_undo_pixels:
            # Skip snapshot for very large layers to preserve stability.
            return
        self._undo_stack.append((self.active_layer, layer.copy()))
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)

    def undo_last(self):
        if not self._undo_stack:
            return
        layer_name, snapshot = self._undo_stack.pop()
        if layer_name in self.annotation_layers:
            self.annotation_layers[layer_name] = snapshot
        self.update()

    def delete_selected_annotation(self):
        if self.selected_annotation_idx is None:
            return
        if 0 <= self.selected_annotation_idx < len(self.vector_annotations):
            del self.vector_annotations[self.selected_annotation_idx]
            self.selected_annotation_idx = None
            self.update()
            self._schedule_autosave()

    def clear_annotations(self):
        if not self.annotation_layers:
            return
        self._push_undo_snapshot()
        for name in self.annotation_layers:
            self.annotation_layers[name].fill(Qt.GlobalColor.transparent)
        self.vector_annotations = []
        self.selected_annotation_idx = None
        self.update()
        self._schedule_autosave()

    def save_annotations(self):
        if not self.annotation_layers:
            return
        self.annotation_dir.mkdir(parents=True, exist_ok=True)
        for name, img in self.annotation_layers.items():
            img.save(str(self._layer_path(name)), "PNG")
        try:
            self._vector_path().write_text(json.dumps(self.vector_annotations, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"vector annotation save error: {e}")
        try:
            payload = {
                "order": list(self.layer_order),
                "settings": self.layer_settings,
            }
            self._layer_settings_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"layer settings save error: {e}")

    def export_marked_copy(self, output_path):
        if self.base_pixmap.isNull():
            return False
        merged = self.base_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        if self.show_annotations:
            painter = QPainter(merged)
            for name in self.layer_order:
                layer_img = self.annotation_layers.get(name)
                settings = self.layer_settings.get(name, {"visible": True, "opacity": 100, "blend": "normal"})
                if not settings.get("visible", True):
                    continue
                if layer_img is not None and not layer_img.isNull():
                    painter.save()
                    painter.setOpacity(float(settings.get("opacity", 100)) / 100.0)
                    painter.setCompositionMode(self._composition_mode_for_layer(name))
                    painter.drawImage(0, 0, layer_img)
                    self._draw_vector_annotations(painter, image_space=True, layer_filter=name)
                    painter.restore()
            painter.end()
        return merged.save(output_path)

    def _compose_current_bgr(self):
        if self.base_pixmap.isNull() or np is None:
            return None
        img = self.base_pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        ptr = img.bits()
        ptr.setsize(img.width() * img.height() * 4)
        rgba = np.frombuffer(ptr, np.uint8).reshape((img.height(), img.width(), 4)).copy()

        # Composite visible layers into RGBA buffer.
        for name in self.layer_order:
            settings = self.layer_settings.get(name, {"visible": True, "opacity": 100, "blend": "normal"})
            if not settings.get("visible", True):
                continue
            layer = self.annotation_layers.get(name)
            if layer is None or layer.isNull() or layer.size() != img.size():
                continue
            l = layer.convertToFormat(QImage.Format.Format_RGBA8888)
            lptr = l.bits()
            lptr.setsize(l.width() * l.height() * 4)
            lrgba = np.frombuffer(lptr, np.uint8).reshape((l.height(), l.width(), 4)).copy()

            alpha = (lrgba[:, :, 3:4].astype(np.float32) / 255.0) * (float(settings.get("opacity", 100)) / 100.0)
            if np.max(alpha) <= 0:
                continue
            base_rgb = rgba[:, :, :3].astype(np.float32)
            top_rgb = lrgba[:, :, :3].astype(np.float32)
            blend = str(settings.get("blend", "normal")).lower()
            if blend == "multiply":
                mixed = (base_rgb * top_rgb) / 255.0
            elif blend == "screen":
                mixed = 255.0 - ((255.0 - base_rgb) * (255.0 - top_rgb) / 255.0)
            elif blend == "overlay":
                low = 2.0 * base_rgb * top_rgb / 255.0
                high = 255.0 - 2.0 * (255.0 - base_rgb) * (255.0 - top_rgb) / 255.0
                mixed = np.where(base_rgb < 128.0, low, high)
            else:
                mixed = top_rgb
            out = base_rgb * (1.0 - alpha) + mixed * alpha
            rgba[:, :, :3] = np.clip(out, 0, 255).astype(np.uint8)

        return cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)

    def _soft_brush_mask(self, w, h, cx, cy, radius, hardness=None, opacity=None, flow=None):
        yy, xx = np.ogrid[:h, :w]
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        radius = max(1.0, float(radius))
        hard_val = float(self.brush_hardness if hardness is None else hardness)
        hard = hard_val / 100.0
        inner = radius * hard
        mask = np.zeros((h, w), dtype=np.float32)
        full = dist <= inner
        fade = (dist > inner) & (dist <= radius)
        mask[full] = 1.0
        if np.any(fade):
            denom = max(1e-6, radius - inner)
            mask[fade] = 1.0 - ((dist[fade] - inner) / denom)
        op = float(self.brush_opacity if opacity is None else opacity)
        fl = float(self.brush_flow if flow is None else flow)
        strength = (op / 100.0) * (fl / 100.0)
        return np.clip(mask * strength, 0.0, 1.0)

    def _apply_effect_brush_point(self, ix, iy):
        if cv2 is None or np is None:
            return
        layer = self._active_layer_image()
        if layer is None or layer.isNull():
            return
        bgr = self._compose_current_bgr()
        if bgr is None:
            return

        h, w = bgr.shape[:2]
        dyn = self._effective_brush_params()
        radius = max(2, int(dyn["width"]))
        x0, y0 = max(0, ix - radius), max(0, iy - radius)
        x1, y1 = min(w, ix + radius + 1), min(h, iy + radius + 1)
        if x1 <= x0 or y1 <= y0:
            return

        roi = bgr[y0:y1, x0:x1].copy()
        mh, mw = roi.shape[:2]
        cx, cy = ix - x0, iy - y0
        mask = self._soft_brush_mask(mw, mh, cx, cy, radius, hardness=dyn["hardness"], opacity=dyn["opacity"], flow=dyn["flow"])
        if np.max(mask) <= 0:
            return

        if self.tool_mode == "blemish_brush":
            inpaint_mask = (mask > 0.1).astype(np.uint8) * 255
            processed = cv2.inpaint(roi, inpaint_mask, inpaintRadius=3.0, flags=cv2.INPAINT_TELEA)
        elif self.tool_mode == "blur_brush":
            k = max(3, (radius // 2) * 2 + 1)
            processed = cv2.GaussianBlur(roi, (k, k), 0)
        elif self.tool_mode == "clone_stamp":
            if self.clone_source_point is None or self.clone_anchor_start is None:
                return
            dx = ix - self.clone_anchor_start[0]
            dy = iy - self.clone_anchor_start[1]
            sx = self.clone_source_point[0] + dx
            sy = self.clone_source_point[1] + dy
            s0x, s0y = max(0, sx - radius), max(0, sy - radius)
            s1x, s1y = min(w, sx + radius + 1), min(h, sy + radius + 1)
            if s1x <= s0x or s1y <= s0y:
                return
            sample = bgr[s0y:s1y, s0x:s1x]
            processed = np.zeros_like(roi)
            ph = min(processed.shape[0], sample.shape[0])
            pw = min(processed.shape[1], sample.shape[1])
            processed[:ph, :pw] = sample[:ph, :pw]
        else:
            return

        mixed = roi.astype(np.float32) * (1.0 - mask[:, :, None]) + processed.astype(np.float32) * mask[:, :, None]
        mixed = np.clip(mixed, 0, 255).astype(np.uint8)
        rgba = cv2.cvtColor(mixed, cv2.COLOR_BGR2RGBA)
        rgba[:, :, 3] = np.clip(mask * 255.0, 0, 255).astype(np.uint8)

        qimg = QImage(rgba.data, rgba.shape[1], rgba.shape[0], rgba.strides[0], QImage.Format.Format_RGBA8888).copy()
        painter = QPainter(layer)
        if self.brush_mode == "erase":
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        else:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.drawImage(x0, y0, qimg)
        painter.end()

    def _apply_paint_brush_point(self, ix, iy, erase=False):
        layer = self._active_layer_image()
        if layer is None or layer.isNull():
            return
        dyn = self._effective_brush_params()
        radius = max(2, int(dyn["width"]))
        w = layer.width()
        h = layer.height()
        x0, y0 = max(0, ix - radius), max(0, iy - radius)
        x1, y1 = min(w, ix + radius + 1), min(h, iy + radius + 1)
        if x1 <= x0 or y1 <= y0:
            return

        mw = x1 - x0
        mh = y1 - y0
        cx = ix - x0
        cy = iy - y0
        mask = self._soft_brush_mask(mw, mh, cx, cy, radius, hardness=dyn["hardness"], opacity=dyn["opacity"], flow=dyn["flow"])
        if np is None:
            return
        rgba = np.zeros((mh, mw, 4), dtype=np.uint8)
        if erase:
            rgba[:, :, 0:3] = 255
            rgba[:, :, 3] = np.clip(mask * 255.0, 0, 255).astype(np.uint8)
            qimg = QImage(rgba.data, mw, mh, rgba.strides[0], QImage.Format.Format_RGBA8888).copy()
            painter = QPainter(layer)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            painter.drawImage(x0, y0, qimg)
            painter.end()
            return

        base_alpha = float(self.markup_color.alpha()) / 255.0
        rgba[:, :, 0] = self.markup_color.red()
        rgba[:, :, 1] = self.markup_color.green()
        rgba[:, :, 2] = self.markup_color.blue()
        rgba[:, :, 3] = np.clip(mask * base_alpha * 255.0, 0, 255).astype(np.uint8)
        qimg = QImage(rgba.data, mw, mh, rgba.strides[0], QImage.Format.Format_RGBA8888).copy()
        painter = QPainter(layer)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.drawImage(x0, y0, qimg)
        painter.end()

    def _apply_paint_brush_line(self, start_pt, end_pt, erase=False):
        if start_pt is None or end_pt is None:
            return
        x0, y0 = float(start_pt[0]), float(start_pt[1])
        x1, y1 = float(end_pt[0]), float(end_pt[1])
        dx = x1 - x0
        dy = y1 - y0
        dist = max(abs(dx), abs(dy))
        dyn = self._effective_brush_params()
        spacing = max(1.0, float(dyn["width"]) * 0.35)
        steps = max(1, int(dist / spacing))
        for i in range(steps + 1):
            t = float(i) / float(steps)
            xi = int(x0 + dx * t)
            yi = int(y0 + dy * t)
            self._apply_paint_brush_point(xi, yi, erase=erase)

    def _apply_effect_brush_line(self, start_pt, end_pt):
        if start_pt is None or end_pt is None:
            return
        x0, y0 = int(start_pt[0]), int(start_pt[1])
        x1, y1 = int(end_pt[0]), int(end_pt[1])
        dist = max(abs(x1 - x0), abs(y1 - y0))
        dyn = self._effective_brush_params()
        steps = max(1, int(dist / max(1, int(dyn["width"]) // 3)))
        for i in range(steps + 1):
            t = float(i) / float(steps)
            xi = int(x0 + (x1 - x0) * t)
            yi = int(y0 + (y1 - y0) * t)
            self._apply_effect_brush_point(xi, yi)

    def _image_rect(self):
        if self.base_pixmap.isNull():
            return None
        return (
            self.offset_x,
            self.offset_y,
            self.base_pixmap.width() * self.scale_factor,
            self.base_pixmap.height() * self.scale_factor,
        )

    def _widget_to_image(self, pos):
        if self.base_pixmap.isNull():
            return None
        ix = (float(pos.x()) - self.offset_x) / self.scale_factor
        iy = (float(pos.y()) - self.offset_y) / self.scale_factor
        if 0 <= ix < self.base_pixmap.width() and 0 <= iy < self.base_pixmap.height():
            return ix, iy
        return None

    def _to_widget(self, ix, iy):
        return (
            int(self.offset_x + ix * self.scale_factor),
            int(self.offset_y + iy * self.scale_factor),
        )

    def _update_compare_ratio_from_widget_x(self, x_pos):
        rect = self._image_rect()
        if rect is None:
            return
        left = rect[0]
        width = rect[2]
        if width <= 1:
            return
        ratio = (float(x_pos) - left) / width
        self.set_compare_ratio(ratio)

    def _draw_vector_annotations(self, painter, image_space=False, layer_filter=None):
        for idx, ann in enumerate(self.vector_annotations):
            layer = ann.get("layer", "blemish")
            if layer_filter is not None and layer != layer_filter:
                continue
            if "color" in ann and isinstance(ann.get("color"), (list, tuple)) and len(ann.get("color")) >= 4:
                c = ann.get("color")
                color = QColor(int(c[0]), int(c[1]), int(c[2]), int(c[3]))
            else:
                color = self.LAYER_COLORS.get(layer, QColor(255, 0, 0, 210))
            width = max(1, int(ann.get("size", self.pen_width)))
            pen = QPen(color, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(color)

            t = ann.get("type")
            if t == "circle":
                x1, y1 = ann.get("x1", 0), ann.get("y1", 0)
                x2, y2 = ann.get("x2", x1), ann.get("y2", y1)
                if image_space:
                    left, top = min(x1, x2), min(y1, y2)
                    rw, rh = abs(x2 - x1), abs(y2 - y1)
                else:
                    wx1, wy1 = self._to_widget(x1, y1)
                    wx2, wy2 = self._to_widget(x2, y2)
                    left, top = min(wx1, wx2), min(wy1, wy2)
                    rw, rh = abs(wx2 - wx1), abs(wy2 - wy1)
                painter.drawEllipse(int(left), int(top), int(rw), int(rh))
            elif t == "arrow":
                x1, y1 = ann.get("x1", 0), ann.get("y1", 0)
                x2, y2 = ann.get("x2", x1), ann.get("y2", y1)
                if not image_space:
                    x1, y1 = self._to_widget(x1, y1)
                    x2, y2 = self._to_widget(x2, y2)
                self._draw_arrow_on_image(painter, x1, y1, x2, y2)
            elif t == "text":
                x, y = ann.get("x", 0), ann.get("y", 0)
                text = ann.get("text", "")
                if not text:
                    continue
                if not image_space:
                    x, y = self._to_widget(x, y)
                painter.setFont(QFont("Segoe UI", max(10, width * 2), QFont.Weight.Bold))
                painter.drawText(int(x), int(y), text)

            if not image_space and idx == self.selected_annotation_idx and self.tool_mode == "select":
                self._draw_annotation_handles(painter, ann)

    def _draw_annotation_handles(self, painter, ann):
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setBrush(QColor(255, 255, 255, 220))
        t = ann.get("type")
        handle_size = 8
        if t in ("circle", "arrow"):
            points = [
                self._to_widget(ann.get("x1", 0), ann.get("y1", 0)),
                self._to_widget(ann.get("x2", 0), ann.get("y2", 0)),
            ]
            for px, py in points:
                painter.drawRect(px - handle_size // 2, py - handle_size // 2, handle_size, handle_size)
        elif t == "text":
            px, py = self._to_widget(ann.get("x", 0), ann.get("y", 0))
            painter.drawRect(px - handle_size // 2, py - handle_size // 2, handle_size, handle_size)
            text_rect = self._text_rect_in_widget(ann)
            if text_rect is not None:
                rx = text_rect.right()
                by = text_rect.bottom()
                painter.drawRect(rx - handle_size // 2, by - handle_size // 2, handle_size, handle_size)

    def _text_rect_in_widget(self, ann):
        tx, ty = self._to_widget(ann.get("x", 0), ann.get("y", 0))
        text = ann.get("text", "")
        if not text:
            return None
        size = max(6, int(ann.get("size", self.pen_width)))
        font = QFont("Segoe UI", max(10, size * 2), QFont.Weight.Bold)
        metrics = QFontMetrics(font)
        w = max(20, metrics.horizontalAdvance(text))
        h = max(16, metrics.height())
        return QRect(tx - 2, ty - h, w + 6, h + 8)

    def _update_stroke_region(self, a, b=None, pad=10):
        if a is None:
            return
        if b is None:
            b = a
        ax, ay = self._to_widget(a[0], a[1])
        bx, by = self._to_widget(b[0], b[1])
        left = min(ax, bx) - pad
        top = min(ay, by) - pad
        right = max(ax, bx) + pad
        bottom = max(ay, by) + pad
        self.update(QRect(left, top, max(1, right - left), max(1, bottom - top)))

    def _annotation_hit(self, pos):
        # Returns (index, hit_mode) where hit_mode is move/resize_start/resize_end.
        px, py = int(pos.x()), int(pos.y())
        handle_radius = 10

        for idx in range(len(self.vector_annotations) - 1, -1, -1):
            ann = self.vector_annotations[idx]
            t = ann.get("type")

            if t in ("circle", "arrow"):
                p1 = self._to_widget(ann.get("x1", 0), ann.get("y1", 0))
                p2 = self._to_widget(ann.get("x2", 0), ann.get("y2", 0))
                if (p1[0] - px) ** 2 + (p1[1] - py) ** 2 <= handle_radius ** 2:
                    return idx, "resize_start"
                if (p2[0] - px) ** 2 + (p2[1] - py) ** 2 <= handle_radius ** 2:
                    return idx, "resize_end"

                left, right = min(p1[0], p2[0]), max(p1[0], p2[0])
                top, bottom = min(p1[1], p2[1]), max(p1[1], p2[1])
                pad = 8
                if left - pad <= px <= right + pad and top - pad <= py <= bottom + pad:
                    return idx, "move"

            elif t == "text":
                rect = self._text_rect_in_widget(ann)
                if rect is None:
                    continue
                tx, ty = self._to_widget(ann.get("x", 0), ann.get("y", 0))
                resize_x = rect.right()
                resize_y = rect.bottom()
                if (resize_x - px) ** 2 + (resize_y - py) ** 2 <= handle_radius ** 2:
                    return idx, "resize_text"
                if rect.contains(px, py):
                    return idx, "move"

        return None, None

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(20, 20, 20))

        if self.base_pixmap.isNull():
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "[Unable to load image]")
            return

        rect = self._image_rect()
        if rect is None:
            return

        x, y, w, h = rect
        target_rect = QRect(int(x), int(y), int(w), int(h))
        if self.compare_enabled and self.compare_pixmap and not self.compare_pixmap.isNull():
            if self.compare_mode == "before":
                painter.drawPixmap(target_rect, self.base_pixmap)
            elif self.compare_mode == "after":
                painter.drawPixmap(target_rect, self.compare_pixmap)
            else:
                split_x = int(target_rect.x() + target_rect.width() * self.compare_ratio)
                left_w = max(1, split_x - target_rect.x())
                right_w = max(1, target_rect.right() - split_x + 1)

                src_full = self.base_pixmap.rect()
                src_left = QRect(
                    src_full.x(),
                    src_full.y(),
                    int(src_full.width() * self.compare_ratio),
                    src_full.height(),
                )
                src_right = QRect(
                    src_left.right() + 1,
                    src_full.y(),
                    max(1, src_full.width() - src_left.width()),
                    src_full.height(),
                )

                painter.drawPixmap(QRect(target_rect.x(), target_rect.y(), left_w, target_rect.height()), self.base_pixmap, src_left)
                painter.drawPixmap(QRect(split_x, target_rect.y(), right_w, target_rect.height()), self.compare_pixmap, src_right)
                painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
                painter.drawLine(split_x, target_rect.top(), split_x, target_rect.bottom())
                painter.setBrush(QColor(255, 255, 255, 235))
                painter.setPen(QPen(QColor(30, 30, 30, 220), 1))
                handle_y = target_rect.top() + target_rect.height() // 2
                painter.drawEllipse(split_x - 8, handle_y - 8, 16, 16)

            # Compare usage hint overlay.
            painter.setPen(QColor(245, 245, 245))
            painter.setBrush(QColor(0, 0, 0, 135))
            hint_rect = QRect(target_rect.x() + 8, target_rect.y() + 8, 340, 24)
            painter.drawRoundedRect(hint_rect, 4, 4)
            painter.drawText(
                hint_rect,
                Qt.AlignmentFlag.AlignCenter,
                "Compare: C cycle mode | R center divider | Drag handle",
            )
        else:
            painter.drawPixmap(target_rect, self.base_pixmap)

        if self.show_annotations:
            for name in self.layer_order:
                layer_img = self.annotation_layers.get(name)
                settings = self.layer_settings.get(name, {"visible": True, "opacity": 100, "blend": "normal"})
                if not settings.get("visible", True):
                    continue
                painter.save()
                painter.setOpacity(float(settings.get("opacity", 100)) / 100.0)
                painter.setCompositionMode(self._composition_mode_for_layer(name))
                if layer_img is not None and not layer_img.isNull():
                    painter.drawImage(target_rect, layer_img)
                self._draw_vector_annotations(painter, image_space=False, layer_filter=name)
                painter.restore()

        if self.shape_start is not None and self.shape_end is not None:
            pen = QPen(self.current_layer_color(), self.pen_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            sx, sy = self.shape_start
            ex, ey = self.shape_end
            sxw = int(self.offset_x + sx * self.scale_factor)
            syw = int(self.offset_y + sy * self.scale_factor)
            exw = int(self.offset_x + ex * self.scale_factor)
            eyw = int(self.offset_y + ey * self.scale_factor)
            if self.tool_mode == "circle":
                left = min(sxw, exw)
                top = min(syw, eyw)
                rw = abs(exw - sxw)
                rh = abs(eyw - syw)
                painter.drawEllipse(left, top, rw, rh)
            elif self.tool_mode == "arrow":
                self._draw_arrow(painter, sxw, syw, exw, eyw)

        # Subtle brush cursor ring (Photoshop-style): outer radius + hardness core.
        if self.cursor_image_point is not None and self.drawing_enabled and self.show_hardness_ring:
            ring_tools = {"pen", "eraser", "blemish_brush", "blur_brush", "clone_stamp"}
            if self.tool_mode in ring_tools:
                cx, cy = self._to_widget(self.cursor_image_point[0], self.cursor_image_point[1])
                dyn = self._effective_brush_params()
                outer_r = max(2, int(dyn["width"]))
                hard = max(1, min(100, int(dyn["hardness"])))
                inner_r = max(1, int(outer_r * (hard / 100.0)))

                painter.save()
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(255, 255, 255, 110), 1))
                painter.drawEllipse(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)
                painter.setPen(QPen(QColor(255, 255, 255, 55), 1))
                painter.drawEllipse(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2)
                painter.restore()

    def _draw_arrow(self, painter, x1, y1, x2, y2):
        painter.drawLine(x1, y1, x2, y2)
        angle = math.atan2(y2 - y1, x2 - x1)
        size = max(8, int(self.pen_width * 2.4))
        left = (x2 - size * math.cos(angle - math.pi / 6), y2 - size * math.sin(angle - math.pi / 6))
        right = (x2 - size * math.cos(angle + math.pi / 6), y2 - size * math.sin(angle + math.pi / 6))
        painter.setBrush(self.current_layer_color())
        painter.drawPolygon(QPolygonF([
            QPointF(float(x2), float(y2)),
            QPointF(float(left[0]), float(left[1])),
            QPointF(float(right[0]), float(right[1])),
        ]))

    def _draw_arrow_on_image(self, painter, x1, y1, x2, y2):
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        angle = math.atan2(y2 - y1, x2 - x1)
        size = max(6, int(self.pen_width * 2.2))
        left = (x2 - size * math.cos(angle - math.pi / 6), y2 - size * math.sin(angle - math.pi / 6))
        right = (x2 - size * math.cos(angle + math.pi / 6), y2 - size * math.sin(angle + math.pi / 6))
        painter.setBrush(self.current_layer_color())
        painter.drawPolygon(QPolygonF([
            QPointF(float(x2), float(y2)),
            QPointF(float(left[0]), float(left[1])),
            QPointF(float(right[0]), float(right[1])),
        ]))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = True
            self.last_pan_pos = event.position()
            event.accept()
            return

        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.compare_enabled
            and self.compare_mode == "split"
            and self.compare_pixmap
            and not self.compare_pixmap.isNull()
        ):
            rect = self._image_rect()
            if rect is not None:
                split_x = rect[0] + rect[2] * self.compare_ratio
                x = float(event.position().x())
                y = float(event.position().y())
                if abs(x - split_x) <= 12 and rect[1] <= y <= (rect[1] + rect[3]):
                    self.compare_dragging = True
                    self._update_compare_ratio_from_widget_x(x)
                    event.accept()
                    return

        if event.button() == Qt.MouseButton.LeftButton and self.space_pan_enabled:
            self.panning = True
            self.last_pan_pos = event.position()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.tool_mode == "select":
            if self.is_layer_locked(self.active_layer):
                event.accept()
                return
            idx, mode = self._annotation_hit(event.position())
            self.selected_annotation_idx = idx
            if idx is not None and mode is not None:
                self._drag_mode = mode
                img_point = self._widget_to_image(event.position())
                self._drag_start_point = img_point
                self._drag_original_annotation = dict(self.vector_annotations[idx])
            else:
                self._drag_mode = None
                self._drag_start_point = None
                self._drag_original_annotation = None
            self.update()
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.drawing_enabled:
            if self.is_layer_locked(self.active_layer):
                event.accept()
                return
            img_point = self._widget_to_image(event.position())
            if img_point is not None:
                self._push_undo_snapshot()
                if self.tool_mode == "clone_stamp" and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
                    self.clone_source_point = (int(img_point[0]), int(img_point[1]))
                    self.clone_anchor_start = None
                    self.drawing = False
                    self.update()
                    event.accept()
                    return
                if self.tool_mode in ("circle", "arrow"):
                    self.shape_start = img_point
                    self.shape_end = img_point
                    self.drawing = True
                elif self.tool_mode == "text":
                    text = ""
                    if self.text_provider:
                        text = self.text_provider()
                    if text:
                        self.vector_annotations.append({
                            "type": "text",
                            "layer": self.active_layer,
                            "x": float(img_point[0]),
                            "y": float(img_point[1]),
                            "text": text,
                            "size": int(self.pen_width),
                            "color": [self.markup_color.red(), self.markup_color.green(), self.markup_color.blue(), self.markup_color.alpha()],
                        })
                        self.selected_annotation_idx = len(self.vector_annotations) - 1
                        self.update()
                        self._schedule_autosave()
                    self.drawing = False
                else:
                    self.drawing = True
                    self.last_draw_point = img_point
                    layer = self._active_layer_image()
                    eraser_override = bool(self._tablet_in_proximity and self.tablet_eraser_detection and self._tablet_eraser_active)
                    if self.tool_mode == "clone_stamp":
                        self.clone_anchor_start = (int(img_point[0]), int(img_point[1]))
                    if self.tool_mode in ("blemish_brush", "blur_brush", "clone_stamp") and not eraser_override:
                        self._apply_effect_brush_point(int(img_point[0]), int(img_point[1]))
                        self._update_stroke_region(img_point, img_point, pad=max(10, int(self.pen_width * self.scale_factor + 8)))
                        self._schedule_autosave()
                    elif self.tool_mode in ("pen", "eraser") and layer is not None and not layer.isNull():
                        self._apply_paint_brush_point(int(img_point[0]), int(img_point[1]), erase=(self.tool_mode == "eraser" or eraser_override))
                        self._update_stroke_region(img_point, img_point, pad=max(10, int(self.pen_width * self.scale_factor + 8)))
                        self._schedule_autosave()
                    elif eraser_override and layer is not None and not layer.isNull():
                        self._apply_paint_brush_point(int(img_point[0]), int(img_point[1]), erase=True)
                        self._update_stroke_region(img_point, img_point, pad=max(10, int(self.pen_width * self.scale_factor + 8)))
                        self._schedule_autosave()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        hover_point = self._widget_to_image(event.position())
        self.cursor_image_point = hover_point

        if self.compare_dragging:
            self._update_compare_ratio_from_widget_x(event.position().x())
            event.accept()
            return

        if self.panning and self.last_pan_pos is not None:
            delta = event.position() - self.last_pan_pos
            self.offset_x += float(delta.x())
            self.offset_y += float(delta.y())
            self.last_pan_pos = event.position()
            self.update()
            event.accept()
            return

        if self.tool_mode == "select" and self.selected_annotation_idx is not None and self._drag_mode:
            img_point = self._widget_to_image(event.position())
            if img_point is None or self._drag_start_point is None or self._drag_original_annotation is None:
                event.accept()
                return

            ann = dict(self._drag_original_annotation)
            dx = float(img_point[0] - self._drag_start_point[0])
            dy = float(img_point[1] - self._drag_start_point[1])

            if self._drag_mode == "move":
                if ann.get("type") in ("circle", "arrow"):
                    ann["x1"] = float(ann.get("x1", 0) + dx)
                    ann["y1"] = float(ann.get("y1", 0) + dy)
                    ann["x2"] = float(ann.get("x2", 0) + dx)
                    ann["y2"] = float(ann.get("y2", 0) + dy)
                elif ann.get("type") == "text":
                    ann["x"] = float(ann.get("x", 0) + dx)
                    ann["y"] = float(ann.get("y", 0) + dy)
            elif self._drag_mode == "resize_start":
                ann["x1"] = float(img_point[0])
                ann["y1"] = float(img_point[1])
            elif self._drag_mode == "resize_end":
                ann["x2"] = float(img_point[0])
                ann["y2"] = float(img_point[1])
            elif self._drag_mode == "resize_text":
                base = max(6, int(self._drag_original_annotation.get("size", self.pen_width)))
                new_size = max(6, base + int(dy / 2.0))
                ann["size"] = int(new_size)

            self.vector_annotations[self.selected_annotation_idx] = ann
            self.update()
            event.accept()
            return

        layer = self._active_layer_image()
        if self.drawing and self.drawing_enabled and layer is not None and not layer.isNull():
            img_point = self._widget_to_image(event.position())
            if img_point is not None:
                if self.tool_mode in ("circle", "arrow") and self.shape_start is not None:
                    self.shape_end = img_point
                    self.update()
                    event.accept()
                    return

                if self.last_draw_point is None:
                    event.accept()
                    return

                eraser_override = bool(self._tablet_in_proximity and self.tablet_eraser_detection and self._tablet_eraser_active)

                if self.tool_mode in ("blemish_brush", "blur_brush", "clone_stamp") and not eraser_override:
                    self._apply_effect_brush_line(self.last_draw_point, img_point)
                    prev = self.last_draw_point
                    self.last_draw_point = img_point
                    self._update_stroke_region(prev, img_point, pad=max(10, int(self.pen_width * self.scale_factor + 8)))
                    self._schedule_autosave()
                    event.accept()
                    return

                self._apply_paint_brush_line(self.last_draw_point, img_point, erase=(self.tool_mode == "eraser" or eraser_override))
                prev = self.last_draw_point
                self.last_draw_point = img_point
                self._update_stroke_region(prev, img_point, pad=max(10, int(self.pen_width * self.scale_factor + 8)))
                self._schedule_autosave()
            event.accept()
            return

        super().mouseMoveEvent(event)

        # Keep cursor ring responsive while hovering.
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.compare_dragging:
            self.compare_dragging = False
            event.accept()
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = False
            self.last_pan_pos = None
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.space_pan_enabled:
                self.panning = False
                self.last_pan_pos = None
                event.accept()
                return

            if self.tool_mode == "select":
                if self._drag_mode is not None:
                    self._schedule_autosave()
                self._drag_mode = None
                self._drag_start_point = None
                self._drag_original_annotation = None
                event.accept()
                return

            if self.drawing and self.tool_mode in ("circle", "arrow"):
                layer = self._active_layer_image()
                if layer is not None and not layer.isNull() and self.shape_start and self.shape_end:
                    sx, sy = self.shape_start
                    ex, ey = self.shape_end
                    self.vector_annotations.append({
                        "type": self.tool_mode,
                        "layer": self.active_layer,
                        "x1": float(sx),
                        "y1": float(sy),
                        "x2": float(ex),
                        "y2": float(ey),
                        "size": int(self.pen_width),
                        "color": [self.markup_color.red(), self.markup_color.green(), self.markup_color.blue(), self.markup_color.alpha()],
                    })
                    self.selected_annotation_idx = len(self.vector_annotations) - 1
                    self.update()
                    self._schedule_autosave()
                self.shape_start = None
                self.shape_end = None
            self.drawing = False
            self.last_draw_point = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def tabletEvent(self, event):
        if not self.tablet_enabled:
            event.ignore()
            return

        self._tablet_in_proximity = True
        self._tablet_pressure = max(0.0, min(1.0, float(event.pressure())))
        # Light smoothing avoids jitter while preserving stroke responsiveness.
        self._tablet_pressure_filtered = (self._tablet_pressure_filtered * 0.55) + (self._tablet_pressure * 0.45)
        self._tablet_tilt_x = float(getattr(event, "xTilt", lambda: 0)())
        self._tablet_tilt_y = float(getattr(event, "yTilt", lambda: 0)())
        pointer_type = getattr(event, "pointerType", lambda: None)()
        self._tablet_eraser_active = bool(self.tablet_eraser_detection and pointer_type == QTabletEvent.PointerType.Eraser)

        img_point = self._widget_to_image(event.position())
        self.cursor_image_point = img_point
        t = event.type()

        if t == QEvent.Type.TabletPress:
            if self.tool_mode == "select":
                if self.is_layer_locked(self.active_layer):
                    event.accept()
                    return
                idx, mode = self._annotation_hit(event.position())
                self.selected_annotation_idx = idx
                if idx is not None and mode is not None:
                    self._drag_mode = mode
                    self._drag_start_point = img_point
                    self._drag_original_annotation = dict(self.vector_annotations[idx])
                else:
                    self._drag_mode = None
                    self._drag_start_point = None
                    self._drag_original_annotation = None
                self.update()
                event.accept()
                return

            if self.drawing_enabled and img_point is not None:
                if self.is_layer_locked(self.active_layer):
                    event.accept()
                    return
                self._push_undo_snapshot()
                if self.tool_mode == "clone_stamp" and (event.modifiers() & Qt.KeyboardModifier.AltModifier):
                    self.clone_source_point = (int(img_point[0]), int(img_point[1]))
                    self.clone_anchor_start = None
                    self.drawing = False
                    self.update()
                    event.accept()
                    return

                if self.tool_mode in ("circle", "arrow"):
                    self.shape_start = img_point
                    self.shape_end = img_point
                    self.drawing = True
                    event.accept()
                    return

                if self.tool_mode == "text":
                    text = self.text_provider() if self.text_provider else ""
                    if text:
                        self.vector_annotations.append({
                            "type": "text",
                            "layer": self.active_layer,
                            "x": float(img_point[0]),
                            "y": float(img_point[1]),
                            "text": text,
                            "size": int(self.pen_width),
                            "color": [self.markup_color.red(), self.markup_color.green(), self.markup_color.blue(), self.markup_color.alpha()],
                        })
                        self.selected_annotation_idx = len(self.vector_annotations) - 1
                        self.update()
                        self._schedule_autosave()
                    self.drawing = False
                    event.accept()
                    return

                self.drawing = True
                self.last_draw_point = img_point
                eraser_override = bool(self.tablet_eraser_detection and self._tablet_eraser_active)
                if self.tool_mode == "clone_stamp":
                    self.clone_anchor_start = (int(img_point[0]), int(img_point[1]))

                if self.tool_mode in ("blemish_brush", "blur_brush", "clone_stamp") and not eraser_override:
                    self._apply_effect_brush_point(int(img_point[0]), int(img_point[1]))
                else:
                    self._apply_paint_brush_point(int(img_point[0]), int(img_point[1]), erase=(self.tool_mode == "eraser" or eraser_override))
                self._update_stroke_region(img_point, img_point, pad=max(10, int(self.pen_width * self.scale_factor + 8)))
                self._schedule_autosave()
                event.accept()
                return

        elif t == QEvent.Type.TabletMove:
            if self.tool_mode == "select" and self.selected_annotation_idx is not None and self._drag_mode:
                if img_point is None or self._drag_start_point is None or self._drag_original_annotation is None:
                    event.accept()
                    return
                ann = dict(self._drag_original_annotation)
                dx = float(img_point[0] - self._drag_start_point[0])
                dy = float(img_point[1] - self._drag_start_point[1])
                if self._drag_mode == "move":
                    if ann.get("type") in ("circle", "arrow"):
                        ann["x1"] = float(ann.get("x1", 0) + dx)
                        ann["y1"] = float(ann.get("y1", 0) + dy)
                        ann["x2"] = float(ann.get("x2", 0) + dx)
                        ann["y2"] = float(ann.get("y2", 0) + dy)
                    elif ann.get("type") == "text":
                        ann["x"] = float(ann.get("x", 0) + dx)
                        ann["y"] = float(ann.get("y", 0) + dy)
                elif self._drag_mode == "resize_start":
                    ann["x1"] = float(img_point[0])
                    ann["y1"] = float(img_point[1])
                elif self._drag_mode == "resize_end":
                    ann["x2"] = float(img_point[0])
                    ann["y2"] = float(img_point[1])
                elif self._drag_mode == "resize_text":
                    base = max(6, int(self._drag_original_annotation.get("size", self.pen_width)))
                    ann["size"] = int(max(6, base + int(dy / 2.0)))
                self.vector_annotations[self.selected_annotation_idx] = ann
                self.update()
                event.accept()
                return

            layer = self._active_layer_image()
            if self.drawing and self.drawing_enabled and layer is not None and not layer.isNull() and img_point is not None:
                if self.tool_mode in ("circle", "arrow") and self.shape_start is not None:
                    self.shape_end = img_point
                    self.update()
                    event.accept()
                    return
                if self.last_draw_point is None:
                    event.accept()
                    return

                eraser_override = bool(self.tablet_eraser_detection and self._tablet_eraser_active)
                if self.tool_mode in ("blemish_brush", "blur_brush", "clone_stamp") and not eraser_override:
                    self._apply_effect_brush_line(self.last_draw_point, img_point)
                else:
                    self._apply_paint_brush_line(self.last_draw_point, img_point, erase=(self.tool_mode == "eraser" or eraser_override))
                prev = self.last_draw_point
                self.last_draw_point = img_point
                self._update_stroke_region(prev, img_point, pad=max(10, int(self.pen_width * self.scale_factor + 8)))
                self._schedule_autosave()
                event.accept()
                return

        elif t == QEvent.Type.TabletRelease:
            if self.tool_mode == "select":
                if self._drag_mode is not None:
                    self._schedule_autosave()
                self._drag_mode = None
                self._drag_start_point = None
                self._drag_original_annotation = None
                event.accept()
                return

            if self.drawing and self.tool_mode in ("circle", "arrow"):
                layer = self._active_layer_image()
                if layer is not None and not layer.isNull() and self.shape_start and self.shape_end:
                    sx, sy = self.shape_start
                    ex, ey = self.shape_end
                    self.vector_annotations.append({
                        "type": self.tool_mode,
                        "layer": self.active_layer,
                        "x1": float(sx),
                        "y1": float(sy),
                        "x2": float(ex),
                        "y2": float(ey),
                        "size": int(self.pen_width),
                        "color": [self.markup_color.red(), self.markup_color.green(), self.markup_color.blue(), self.markup_color.alpha()],
                    })
                    self.selected_annotation_idx = len(self.vector_annotations) - 1
                    self.update()
                    self._schedule_autosave()
                self.shape_start = None
                self.shape_end = None

            self.drawing = False
            self.last_draw_point = None
            self._tablet_eraser_active = False
            self._tablet_pressure = 1.0
            self._tablet_pressure_filtered = 1.0
            event.accept()
            return

        event.accept()

    def leaveEvent(self, event):
        self.cursor_image_point = None
        self.update()
        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_BracketLeft:  # [
            self.set_pen_width(self.pen_width - 5)
            event.accept()
            return
        elif event.key() == Qt.Key.Key_BracketRight:  # ]
            self.set_pen_width(self.pen_width + 5)
            event.accept()
            return
        elif event.key() == Qt.Key.Key_H:  # H toggles hardness ring
            self.show_hardness_ring = not self.show_hardness_ring
            self.update()
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        # Keyboard shortcut: Ctrl+Wheel zoom. Also allow middle-hold + wheel.
        buttons = QApplication.mouseButtons()
        allow_zoom = (
            bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            or bool(buttons & Qt.MouseButton.MiddleButton)
        )
        if not allow_zoom:
            super().wheelEvent(event)
            return

        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.1 if delta > 0 else 0.9
        self.adjust_zoom(factor, anchor=event.position())
        event.accept()


class RelightWorker(QThread):
    completed = pyqtSignal(bool, str, object)

    def __init__(self, canvas, source_bgr, prompt_text, backend):
        super().__init__()
        self.canvas = canvas
        self.source_bgr = source_bgr
        self.prompt_text = prompt_text
        self.backend = backend

    def run(self):
        try:
            out, err = self.canvas.compute_relight_image(self.source_bgr, self.prompt_text, self.backend)
            if out is None:
                self.completed.emit(False, err or "Relight failed", None)
            else:
                # Detect silent near-identical outputs and report clearly.
                src = self.source_bgr.astype(np.float32)
                dst = out.astype(np.float32)
                mad = float(np.mean(np.abs(dst - src)))
                src_l = cv2.cvtColor(self.source_bgr, cv2.COLOR_BGR2LAB)[:, :, 0].astype(np.float32)
                dst_l = cv2.cvtColor(out, cv2.COLOR_BGR2LAB)[:, :, 0].astype(np.float32)
                luma_delta = float(np.mean(np.abs(dst_l - src_l)))
                if mad < 2.0 and luma_delta < 2.0:
                    self.completed.emit(
                        False,
                        (
                            "Relight finished but produced almost no visible change. "
                            f"delta={mad:.2f}, luma={luma_delta:.2f}. "
                            "Try Local Fallback backend or a stronger prompt."
                        ),
                        None,
                    )
                    return
                self.completed.emit(True, "ok", out)
        except Exception as e:
            self.completed.emit(False, f"Relight worker error: {e}", None)


class ImageLightboxDialog(QDialog):
    """Image popup with mouse pan/zoom, annotations, and right-side notes."""

    def __init__(self, filepath, photo_id, db, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.photo_id = photo_id
        self.db = db
        self._did_initial_fit = False
        self._unsaved_image_changes = False
        self._retouch_result_pixmap = None
        self._retouch_history = []
        self._last_retouch_settings = {"algorithm": "telea", "radius": 3, "padding": 2}
        self._relight_worker = None
        self._relight_progress = None
        self._relight_cancelled = False
        self._relight_target_layer = None
        self._relight_prompt_text = ""

        cache_dir = getattr(parent, 'cache_dir', Path("thumbnail_cache"))
        self.annotation_dir = Path(cache_dir) / "annotations"
        self.compare_path = None

        self.setWindowTitle(f"Photo {photo_id:06d}")
        self.resize(1300, 900)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_notes)

        self._build_ui()
        self._load_notes()
        self._try_load_autosave_project()

    def _log_editor_error(self, action, exc):
        try:
            _append_error_log(
                f"{action} photo_id={self.photo_id} file={self.filepath}",
                type(exc),
                exc,
                exc.__traceback__,
            )
        except Exception:
            pass

    def _build_ui(self):
        root = QVBoxLayout(self)

        self.image_canvas = AnnotatedImageCanvas(self.filepath, self.annotation_dir, self.photo_id)
        self.image_canvas.zoom_changed.connect(self._on_zoom_changed)
        self.image_canvas.set_text_provider(self._request_annotation_text)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        editor_panel = QWidget()
        editor_panel.setMinimumWidth(320)
        editor_panel.setMaximumWidth(440)
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(6, 6, 6, 6)

        nav_group = QGroupBox("View")
        nav_layout = QHBoxLayout(nav_group)
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setIcon(_icon('zoom_out'))
        zoom_out_btn.setIconSize(QSize(14, 14))
        zoom_out_btn.clicked.connect(lambda: self.image_canvas.adjust_zoom(0.9))
        nav_layout.addWidget(zoom_out_btn)
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setIcon(_icon('zoom_in'))
        zoom_in_btn.setIconSize(QSize(14, 14))
        zoom_in_btn.clicked.connect(lambda: self.image_canvas.adjust_zoom(1.1))
        nav_layout.addWidget(zoom_in_btn)
        fit_btn = QPushButton("Fit")
        fit_btn.setIcon(_icon('expand'))
        fit_btn.setIconSize(QSize(14, 14))
        fit_btn.clicked.connect(self.image_canvas.fit_to_view)
        nav_layout.addWidget(fit_btn)
        reset_btn = QPushButton("100%")
        reset_btn.setIcon(_icon('thumbnail_grid'))
        reset_btn.setIconSize(QSize(14, 14))
        reset_btn.clicked.connect(lambda: self.image_canvas.set_zoom(1.0))
        nav_layout.addWidget(reset_btn)
        self.zoom_label = QLabel("100%")
        nav_layout.addWidget(self.zoom_label)
        editor_layout.addWidget(nav_group)

        tool_group = QGroupBox("Tools")
        tool_layout = QVBoxLayout(tool_group)

        tool_layout.addWidget(QLabel("Brush Tools"))
        row1 = QHBoxLayout()
        self.blemish_brush_btn = QPushButton("Blemish")
        self.blemish_brush_btn.setIcon(_icon('batch_retouch'))
        self.blemish_brush_btn.setIconSize(QSize(14, 14))
        self.blemish_brush_btn.setCheckable(True)
        self.blemish_brush_btn.toggled.connect(lambda checked, b=self.blemish_brush_btn: self._set_shape_tool("blemish_brush", checked, b))
        row1.addWidget(self.blemish_brush_btn)
        self.blur_brush_btn = QPushButton("Blur")
        self.blur_brush_btn.setIcon(_icon('subtle'))
        self.blur_brush_btn.setIconSize(QSize(14, 14))
        self.blur_brush_btn.setCheckable(True)
        self.blur_brush_btn.toggled.connect(lambda checked, b=self.blur_brush_btn: self._set_shape_tool("blur_brush", checked, b))
        row1.addWidget(self.blur_brush_btn)
        self.clone_stamp_btn = QPushButton("Clone")
        self.clone_stamp_btn.setIcon(_icon('copy'))
        self.clone_stamp_btn.setIconSize(QSize(14, 14))
        self.clone_stamp_btn.setCheckable(True)
        self.clone_stamp_btn.toggled.connect(lambda checked, b=self.clone_stamp_btn: self._set_shape_tool("clone_stamp", checked, b))
        row1.addWidget(self.clone_stamp_btn)
        tool_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Size:"))
        self.pen_size = QSpinBox()
        self.pen_size.setRange(1, 60)
        self.pen_size.setValue(12)
        self.pen_size.valueChanged.connect(self.image_canvas.set_pen_width)
        row2.addWidget(self.pen_size)
        row2.addWidget(QLabel("Hardness:"))
        self.brush_hardness = QSlider(Qt.Orientation.Horizontal)
        self.brush_hardness.setRange(1, 100)
        self.brush_hardness.setValue(65)
        self.brush_hardness.valueChanged.connect(self.image_canvas.set_brush_hardness)
        row2.addWidget(self.brush_hardness)
        tool_layout.addLayout(row2)

        brush_hint = QLabel("Shortcuts: `[` / `]` size, `H` toggle ring")
        brush_hint.setWordWrap(True)
        brush_hint.setStyleSheet("color: #888; font-size: 10px;")
        tool_layout.addWidget(brush_hint)

        row2b = QHBoxLayout()
        row2b.addWidget(QLabel("Opacity:"))
        self.brush_opacity = QSlider(Qt.Orientation.Horizontal)
        self.brush_opacity.setRange(1, 100)
        self.brush_opacity.setValue(100)
        self.brush_opacity.valueChanged.connect(self.image_canvas.set_brush_opacity)
        row2b.addWidget(self.brush_opacity)
        self.brush_opacity_label = QLabel("100%")
        self.brush_opacity.valueChanged.connect(lambda v: self.brush_opacity_label.setText(f"{int(v)}%"))
        row2b.addWidget(self.brush_opacity_label)
        row2b.addWidget(QLabel("Flow:"))
        self.brush_flow = QSlider(Qt.Orientation.Horizontal)
        self.brush_flow.setRange(1, 100)
        self.brush_flow.setValue(100)
        self.brush_flow.valueChanged.connect(self.image_canvas.set_brush_flow)
        row2b.addWidget(self.brush_flow)
        self.brush_flow_label = QLabel("100%")
        self.brush_flow.valueChanged.connect(lambda v: self.brush_flow_label.setText(f"{int(v)}%"))
        row2b.addWidget(self.brush_flow_label)
        row2b.addWidget(QLabel("Mode:"))
        self.brush_mode_combo = QComboBox()
        self.brush_mode_combo.addItems(["normal", "erase"])
        self.brush_mode_combo.currentTextChanged.connect(self.image_canvas.set_brush_mode)
        row2b.addWidget(self.brush_mode_combo)
        tool_layout.addLayout(row2b)

        row2c = QHBoxLayout()
        self.tablet_enable_chk = QCheckBox("Use Tablet Pressure")
        self.tablet_enable_chk.setChecked(True)
        self.tablet_enable_chk.toggled.connect(self.image_canvas.set_tablet_enabled)
        row2c.addWidget(self.tablet_enable_chk)
        row2c.addWidget(QLabel("Pressure Curve:"))
        self.tablet_curve = QSlider(Qt.Orientation.Horizontal)
        self.tablet_curve.setRange(10, 200)
        self.tablet_curve.setValue(135)
        self.tablet_curve.valueChanged.connect(self.image_canvas.set_tablet_pressure_curve)
        row2c.addWidget(self.tablet_curve)
        self.tablet_curve_label = QLabel("1.35x")
        self.tablet_curve.valueChanged.connect(lambda v: self.tablet_curve_label.setText(f"{float(v)/100.0:.2f}x"))
        row2c.addWidget(self.tablet_curve_label)
        tool_layout.addLayout(row2c)

        row2d = QHBoxLayout()
        self.tablet_tilt_chk = QCheckBox("Tilt Dynamics")
        self.tablet_tilt_chk.setChecked(True)
        self.tablet_tilt_chk.toggled.connect(self.image_canvas.set_tablet_tilt_enabled)
        row2d.addWidget(self.tablet_tilt_chk)
        self.tablet_eraser_chk = QCheckBox("Eraser End Detect")
        self.tablet_eraser_chk.setChecked(True)
        self.tablet_eraser_chk.toggled.connect(self.image_canvas.set_tablet_eraser_detection)
        row2d.addWidget(self.tablet_eraser_chk)
        row2d.addStretch()
        tool_layout.addLayout(row2d)

        hint_lbl = QLabel("Clone Stamp: Alt+Click to set source")
        hint_lbl.setStyleSheet("color: #c8c8c8;")
        tool_layout.addWidget(hint_lbl)

        tool_layout.addWidget(QLabel("Markup Tools"))
        row2 = QHBoxLayout()
        self.draw_toggle = QPushButton("Draw")
        self.draw_toggle.setIcon(_icon('pen_draw'))
        self.draw_toggle.setIconSize(QSize(14, 14))
        self.draw_toggle.setCheckable(True)
        self.draw_toggle.toggled.connect(self._on_draw_toggled)
        row2.addWidget(self.draw_toggle)
        self.select_toggle = QPushButton("Select")
        self.select_toggle.setIcon(_icon('cursor_select'))
        self.select_toggle.setIconSize(QSize(14, 14))
        self.select_toggle.setCheckable(True)
        self.select_toggle.toggled.connect(self._on_select_toggled)
        row2.addWidget(self.select_toggle)
        self.eraser_toggle = QPushButton("Eraser")
        self.eraser_toggle.setIcon(_icon('eraser'))
        self.eraser_toggle.setIconSize(QSize(14, 14))
        self.eraser_toggle.setCheckable(True)
        self.eraser_toggle.toggled.connect(lambda checked: self._set_tool_mode("eraser" if checked else "pen"))
        row2.addWidget(self.eraser_toggle)
        tool_layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.circle_btn = QPushButton("Circle")
        self.circle_btn.setIcon(_icon('shape_circle'))
        self.circle_btn.setIconSize(QSize(14, 14))
        self.circle_btn.setCheckable(True)
        self.circle_btn.toggled.connect(lambda checked, b=self.circle_btn: self._set_shape_tool("circle", checked, b))
        row3.addWidget(self.circle_btn)
        self.arrow_btn = QPushButton("Arrow")
        self.arrow_btn.setIcon(_icon('arrow_right'))
        self.arrow_btn.setIconSize(QSize(14, 14))
        self.arrow_btn.setCheckable(True)
        self.arrow_btn.toggled.connect(lambda checked, b=self.arrow_btn: self._set_shape_tool("arrow", checked, b))
        row3.addWidget(self.arrow_btn)
        self.text_btn = QPushButton("Text")
        self.text_btn.setIcon(_icon('text_tool'))
        self.text_btn.setIconSize(QSize(14, 14))
        self.text_btn.setCheckable(True)
        self.text_btn.toggled.connect(lambda checked, b=self.text_btn: self._set_shape_tool("text", checked, b))
        row3.addWidget(self.text_btn)
        tool_layout.addLayout(row3)

        row3b = QHBoxLayout()
        color_btn = QPushButton("Color")
        color_btn.setIcon(_icon('color_picker'))
        color_btn.setIconSize(QSize(14, 14))
        color_btn.clicked.connect(self._pick_markup_color)
        row3b.addWidget(color_btn)
        self.markup_color_preview = QLabel()
        self.markup_color_preview.setFixedSize(24, 16)
        self.markup_color_preview.setStyleSheet("background: rgba(255,60,60,1); border: 1px solid #666;")
        row3b.addWidget(self.markup_color_preview)
        row3b.addStretch()
        tool_layout.addLayout(row3b)

        row4 = QHBoxLayout()
        clear_btn = QPushButton("Clear Marks")
        clear_btn.setIcon(_icon('close'))
        clear_btn.setIconSize(QSize(14, 14))
        clear_btn.clicked.connect(self.image_canvas.clear_annotations)
        row4.addWidget(clear_btn)
        undo_btn = QPushButton("Undo")
        undo_btn.setIcon(_icon('undo'))
        undo_btn.setIconSize(QSize(14, 14))
        undo_btn.clicked.connect(self.image_canvas.undo_last)
        row4.addWidget(undo_btn)
        tool_layout.addLayout(row4)

        self.show_marks_toggle = QPushButton("Show Marks")
        self.show_marks_toggle.setIcon(_icon('eye'))
        self.show_marks_toggle.setIconSize(QSize(14, 14))
        self.show_marks_toggle.setCheckable(True)
        self.show_marks_toggle.setChecked(True)
        self.show_marks_toggle.toggled.connect(self.image_canvas.set_show_annotations)
        tool_layout.addWidget(self.show_marks_toggle)
        editor_layout.addWidget(tool_group)

        retouch_group = QGroupBox("Retouch")
        retouch_layout = QVBoxLayout(retouch_group)
        row5 = QHBoxLayout()
        ai_retouch_btn = QPushButton("Apply AI Retouch")
        ai_retouch_btn.setIcon(_icon('sparkle'))
        ai_retouch_btn.setIconSize(QSize(14, 14))
        ai_retouch_btn.clicked.connect(self.apply_ai_retouch)
        row5.addWidget(ai_retouch_btn)
        self.undo_retouch_btn = QPushButton("Undo Retouch")
        self.undo_retouch_btn.setIcon(_icon('undo'))
        self.undo_retouch_btn.setIconSize(QSize(14, 14))
        self.undo_retouch_btn.setEnabled(False)
        self.undo_retouch_btn.clicked.connect(self.undo_retouch)
        row5.addWidget(self.undo_retouch_btn)
        retouch_layout.addLayout(row5)

        row6 = QHBoxLayout()
        row6.addWidget(QLabel("Algo:"))
        self.retouch_algo_combo = QComboBox()
        self.retouch_algo_combo.addItems(["telea", "ns"])
        self.retouch_algo_combo.setCurrentText("telea")
        self.retouch_algo_combo.setMaximumWidth(80)
        row6.addWidget(self.retouch_algo_combo)
        row6.addWidget(QLabel("Radius:"))
        self.retouch_radius_spin = QSpinBox()
        self.retouch_radius_spin.setRange(1, 12)
        self.retouch_radius_spin.setValue(3)
        self.retouch_radius_spin.setMaximumWidth(55)
        row6.addWidget(self.retouch_radius_spin)
        row6.addWidget(QLabel("Padding:"))
        self.retouch_padding_spin = QSpinBox()
        self.retouch_padding_spin.setRange(0, 12)
        self.retouch_padding_spin.setValue(2)
        self.retouch_padding_spin.setMaximumWidth(55)
        row6.addWidget(self.retouch_padding_spin)
        retouch_layout.addLayout(row6)

        row7 = QHBoxLayout()
        self.preset_subtle_btn = QPushButton("Subtle")
        self.preset_subtle_btn.setIcon(_icon('subtle'))
        self.preset_subtle_btn.setIconSize(QSize(14, 14))
        self.preset_subtle_btn.clicked.connect(lambda: self._apply_retouch_preset("subtle"))
        row7.addWidget(self.preset_subtle_btn)
        self.preset_balanced_btn = QPushButton("Balanced")
        self.preset_balanced_btn.setIcon(_icon('balanced'))
        self.preset_balanced_btn.setIconSize(QSize(14, 14))
        self.preset_balanced_btn.clicked.connect(lambda: self._apply_retouch_preset("balanced"))
        row7.addWidget(self.preset_balanced_btn)
        self.preset_strong_btn = QPushButton("Strong")
        self.preset_strong_btn.setIcon(_icon('strong'))
        self.preset_strong_btn.setIconSize(QSize(14, 14))
        self.preset_strong_btn.clicked.connect(lambda: self._apply_retouch_preset("strong"))
        row7.addWidget(self.preset_strong_btn)
        retouch_layout.addLayout(row7)

        row8 = QHBoxLayout()
        sync_batch_btn = QPushButton("Sync To Batch")
        sync_batch_btn.setIcon(_icon('broadcast'))
        sync_batch_btn.setIconSize(QSize(14, 14))
        sync_batch_btn.clicked.connect(self._sync_settings_to_batch)
        row8.addWidget(sync_batch_btn)
        self.save_image_btn = QPushButton("Save Image")
        self.save_image_btn.setIcon(_icon('save'))
        self.save_image_btn.setIconSize(QSize(14, 14))
        self.save_image_btn.setEnabled(False)
        self.save_image_btn.clicked.connect(self.save_current_image)
        row8.addWidget(self.save_image_btn)
        retouch_layout.addLayout(row8)

        self.unsaved_label = QLabel("Unsaved image changes")
        self.unsaved_label.setStyleSheet("color: #ffb347; font-weight: 600;")
        self.unsaved_label.setVisible(False)
        retouch_layout.addWidget(self.unsaved_label)
        retouch_group.setVisible(False)

        compare_group = QGroupBox("Compare")
        compare_layout = QVBoxLayout(compare_group)
        self.compare_toggle = QCheckBox("Compare")
        self.compare_toggle.toggled.connect(self._on_compare_toggled)
        compare_layout.addWidget(self.compare_toggle)

        self.compare_mode_combo = QComboBox()
        self.compare_mode_combo.addItems(["Split", "Before", "After"])
        self.compare_mode_combo.setCurrentText("Split")
        self.compare_mode_combo.currentTextChanged.connect(self._on_compare_mode_changed)
        self.compare_mode_combo.setVisible(False)
        compare_layout.addWidget(self.compare_mode_combo)

        row9 = QHBoxLayout()
        self.compare_split_btn = QPushButton("Split")
        self.compare_split_btn.setIcon(_icon('compare_split'))
        self.compare_split_btn.setIconSize(QSize(14, 14))
        self.compare_split_btn.setCheckable(True)
        self.compare_split_btn.setChecked(True)
        self.compare_split_btn.clicked.connect(lambda: self._set_compare_mode_chip("Split"))
        row9.addWidget(self.compare_split_btn)
        self.compare_before_btn = QPushButton("Before")
        self.compare_before_btn.setIcon(_icon('arrow_left'))
        self.compare_before_btn.setIconSize(QSize(14, 14))
        self.compare_before_btn.setCheckable(True)
        self.compare_before_btn.clicked.connect(lambda: self._set_compare_mode_chip("Before"))
        row9.addWidget(self.compare_before_btn)
        self.compare_after_btn = QPushButton("After")
        self.compare_after_btn.setIcon(_icon('arrow_right'))
        self.compare_after_btn.setIconSize(QSize(14, 14))
        self.compare_after_btn.setCheckable(True)
        self.compare_after_btn.clicked.connect(lambda: self._set_compare_mode_chip("After"))
        row9.addWidget(self.compare_after_btn)
        compare_layout.addLayout(row9)

        row10 = QHBoxLayout()
        reset_divider_btn = QPushButton("Center Divider")
        reset_divider_btn.setIcon(_icon('compare_split'))
        reset_divider_btn.setIconSize(QSize(14, 14))
        reset_divider_btn.clicked.connect(lambda: self.image_canvas.set_compare_ratio(0.5))
        row10.addWidget(reset_divider_btn)
        compare_btn = QPushButton("Load Edited")
        compare_btn.setIcon(_icon('image'))
        compare_btn.setIconSize(QSize(14, 14))
        compare_btn.clicked.connect(self.load_compare_image)
        row10.addWidget(compare_btn)
        compare_layout.addLayout(row10)

        self.compare_slider = QSlider(Qt.Orientation.Horizontal)
        self.compare_slider.setMinimum(5)
        self.compare_slider.setMaximum(95)
        self.compare_slider.setValue(50)
        self.compare_slider.setFixedWidth(130)
        self.compare_slider.valueChanged.connect(lambda v: self.image_canvas.set_compare_ratio(v / 100.0))
        self.compare_slider.setVisible(False)
        compare_layout.addWidget(self.compare_slider)
        editor_layout.addWidget(compare_group)

        layer_group = QGroupBox("Layers")
        layer_layout = QVBoxLayout(layer_group)
        layer_layout.addWidget(QLabel("Stack (top to bottom):"))
        self.layer_list = QListWidget()
        self.layer_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.layer_list.setMaximumHeight(120)
        self.layer_list.setIconSize(QSize(16, 16))
        self.layer_list.setMouseTracking(True)
        self.layer_list.viewport().setMouseTracking(True)
        self.layer_list.currentItemChanged.connect(self._on_layer_list_current_changed)
        self.layer_list.itemChanged.connect(self._on_layer_list_item_changed)
        self.layer_list.viewport().installEventFilter(self)
        self.layer_list.setToolTip("Click the eye icon to toggle layer visibility")
        layer_layout.addWidget(self.layer_list)

        row12 = QHBoxLayout()
        row12.addWidget(QLabel("Opacity:"))
        self.layer_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.layer_opacity_slider.setRange(0, 100)
        self.layer_opacity_slider.setValue(100)
        self.layer_opacity_slider.valueChanged.connect(self._on_layer_opacity_changed)
        row12.addWidget(self.layer_opacity_slider)
        self.layer_opacity_label = QLabel("100%")
        row12.addWidget(self.layer_opacity_label)
        layer_layout.addLayout(row12)

        row13 = QHBoxLayout()
        row13.addWidget(QLabel("Blend:"))
        self.layer_blend_combo = QComboBox()
        self.layer_blend_combo.addItems(["normal", "multiply", "screen", "overlay"])
        self.layer_blend_combo.currentTextChanged.connect(self._on_layer_blend_changed)
        row13.addWidget(self.layer_blend_combo)
        layer_layout.addLayout(row13)

        row14 = QHBoxLayout()
        layer_up_btn = QPushButton("Move Up")
        layer_up_btn.setIcon(_icon('arrow_up'))
        layer_up_btn.setIconSize(QSize(14, 14))
        layer_up_btn.clicked.connect(lambda: self._move_active_layer(-1))
        row14.addWidget(layer_up_btn)
        layer_down_btn = QPushButton("Move Down")
        layer_down_btn.setIcon(_icon('arrow_down'))
        layer_down_btn.setIconSize(QSize(14, 14))
        layer_down_btn.clicked.connect(lambda: self._move_active_layer(1))
        row14.addWidget(layer_down_btn)
        layer_layout.addLayout(row14)

        row14b = QHBoxLayout()
        add_layer_btn = QPushButton("Add")
        add_layer_btn.setIcon(_icon('preset_add'))
        add_layer_btn.setIconSize(QSize(14, 14))
        add_layer_btn.clicked.connect(self._add_layer)
        row14b.addWidget(add_layer_btn)
        dup_layer_btn = QPushButton("Duplicate")
        dup_layer_btn.setIcon(_icon('copy'))
        dup_layer_btn.setIconSize(QSize(14, 14))
        dup_layer_btn.clicked.connect(self._duplicate_layer)
        row14b.addWidget(dup_layer_btn)
        rename_layer_btn = QPushButton("Rename")
        rename_layer_btn.setIcon(_icon('rename'))
        rename_layer_btn.setIconSize(QSize(14, 14))
        rename_layer_btn.clicked.connect(self._rename_layer)
        row14b.addWidget(rename_layer_btn)
        del_layer_btn = QPushButton("Delete")
        del_layer_btn.setIcon(_icon('trash'))
        del_layer_btn.setIconSize(QSize(14, 14))
        del_layer_btn.clicked.connect(self._delete_layer)
        row14b.addWidget(del_layer_btn)
        layer_layout.addLayout(row14b)

        row14c = QHBoxLayout()
        self.layer_lock_btn = QPushButton("Lock Layer")
        self.layer_lock_btn.setIcon(_icon('lock'))
        self.layer_lock_btn.setIconSize(QSize(14, 14))
        self.layer_lock_btn.clicked.connect(self._toggle_layer_lock)
        row14c.addWidget(self.layer_lock_btn)
        layer_layout.addLayout(row14c)

        row14d = QHBoxLayout()
        save_project_btn = QPushButton("Save Project")
        save_project_btn.setIcon(_icon('save'))
        save_project_btn.setIconSize(QSize(14, 14))
        save_project_btn.clicked.connect(self._save_project)
        row14d.addWidget(save_project_btn)
        load_project_btn = QPushButton("Load Project")
        load_project_btn.setIcon(_icon('image'))
        load_project_btn.setIconSize(QSize(14, 14))
        load_project_btn.clicked.connect(self._load_project)
        row14d.addWidget(load_project_btn)
        row14d.addStretch()
        layer_layout.addLayout(row14d)
        
        project_hint = QLabel("Auto-saves every 5s to *_autosave.json")
        project_hint.setStyleSheet("color: #888; font-size: 10px;")
        layer_layout.addWidget(project_hint)

        row14e = QHBoxLayout()
        row14e.addWidget(QLabel("Lighting prompt:"))
        layer_layout.addLayout(row14e)
        self.lighting_prompt_edit = QLineEdit()
        self.lighting_prompt_edit.setPlaceholderText("Describe desired lighting...")
        self.lighting_prompt_edit.textEdited.connect(self._save_lighting_prompt)
        layer_layout.addWidget(self.lighting_prompt_edit)

        legend = QLabel("Create custom layers and reorder them as needed")
        legend.setStyleSheet("color: #c8c8c8;")
        legend.setWordWrap(True)
        layer_layout.addWidget(legend)
        export_btn = QPushButton("Export Marked Copy")
        export_btn.setIcon(_icon('export'))
        export_btn.setIconSize(QSize(14, 14))
        export_btn.clicked.connect(self.export_marked_copy)
        layer_layout.addWidget(export_btn)
        editor_layout.addWidget(layer_group)

        self.image_canvas.layer_state_changed.connect(self._refresh_layer_controls)
        self._rebuild_layer_combo()
        self._refresh_layer_controls()

        self.draw_toggle.blockSignals(True)
        self.draw_toggle.setChecked(True)
        self.draw_toggle.blockSignals(False)
        self.image_canvas.set_drawing_enabled(True)
        
        self._project_autosave_timer = QTimer()
        self._project_autosave_timer.timeout.connect(self._autosave_project_state)
        self._project_autosave_timer.start(5000)

        editor_layout.addStretch()
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setFrameShape(QFrame.Shape.NoFrame)
        editor_scroll.setWidget(editor_panel)
        splitter.addWidget(editor_scroll)

        image_panel = QWidget()
        image_layout = QVBoxLayout(image_panel)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.addWidget(self.image_canvas)
        splitter.addWidget(image_panel)

        notes_panel = QGroupBox("Notes")
        notes_layout = QVBoxLayout(notes_panel)
        notes_hint = QLabel("These notes sync with the Library pane.")
        notes_hint.setWordWrap(True)
        notes_layout.addWidget(notes_hint)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Add notes for this photo...")
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        notes_layout.addWidget(self.notes_edit)

        notes_layout.addWidget(QLabel("Retouch Checklist"))
        self.retouch_checklist = QListWidget()
        self.retouch_checklist.setMaximumHeight(180)
        default_tasks = [
            "Skin cleanup (blemishes)",
            "Lighting balance",
            "Color correction",
            "Background cleanup",
            "Final retouch pass",
        ]
        for task in default_tasks:
            item = QTableWidgetItem(task)
            self.retouch_checklist.addItem(task)
            lw_item = self.retouch_checklist.item(self.retouch_checklist.count() - 1)
            lw_item.setFlags(lw_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            lw_item.setCheckState(Qt.CheckState.Unchecked)
        self.retouch_checklist.itemChanged.connect(self._on_checklist_changed)
        notes_layout.addWidget(self.retouch_checklist)

        notes_actions = QHBoxLayout()
        export_tasks_btn = QPushButton("Export Tasks")
        export_tasks_btn.setIcon(_icon('export'))
        export_tasks_btn.setIconSize(QSize(16, 16))
        export_tasks_btn.clicked.connect(self.export_task_list)
        notes_actions.addWidget(export_tasks_btn)
        notes_actions.addStretch()
        save_btn = QPushButton("Save Notes")
        save_btn.setIcon(_icon('save'))
        save_btn.setIconSize(QSize(16, 16))
        save_btn.clicked.connect(self.save_notes)
        notes_actions.addWidget(save_btn)
        notes_layout.addLayout(notes_actions)

        splitter.addWidget(notes_panel)
        splitter.setSizes([380, 760, 320])
        root.addWidget(splitter)

        self._init_shortcuts()

    def _init_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.image_canvas.undo_last)
        QShortcut(QKeySequence("E"), self, activated=self._toggle_eraser_shortcut)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self.image_canvas.delete_selected_annotation)
        QShortcut(QKeySequence("C"), self, activated=self._cycle_compare_mode)
        QShortcut(QKeySequence("R"), self, activated=lambda: self.image_canvas.set_compare_ratio(0.5))

    def _toggle_eraser_shortcut(self):
        self.eraser_toggle.setChecked(not self.eraser_toggle.isChecked())

    def _request_annotation_text(self):
        text, ok = QInputDialog.getText(self, "Annotation Text", "Enter annotation:")
        return text.strip() if ok else ""

    def _apply_retouch_preset(self, name):
        presets = {
            "subtle": {"algorithm": "telea", "radius": 2, "padding": 1},
            "balanced": {"algorithm": "telea", "radius": 3, "padding": 2},
            "strong": {"algorithm": "ns", "radius": 5, "padding": 3},
        }
        cfg = presets.get(name)
        if not cfg:
            return
        self.retouch_algo_combo.setCurrentText(cfg["algorithm"])
        self.retouch_radius_spin.setValue(cfg["radius"])
        self.retouch_padding_spin.setValue(cfg["padding"])

    def _sync_settings_to_batch(self):
        settings = {
            "algorithm": self.retouch_algo_combo.currentText(),
            "radius": int(self.retouch_radius_spin.value()),
            "padding": int(self.retouch_padding_spin.value()),
        }
        if self.parent() and hasattr(self.parent(), "set_batch_retouch_settings"):
            self.parent().set_batch_retouch_settings(settings)
            QMessageBox.information(self, "Batch Settings Synced", "Current retouch settings will be used by Batch Retouch.")

    def _set_compare_mode_chip(self, label):
        self.compare_mode_combo.setCurrentText(label)

    def _pick_markup_color(self):
        color = QColorDialog.getColor(self.image_canvas.markup_color, self, "Choose Markup Color")
        if not color.isValid():
            return
        self.image_canvas.set_markup_color(color)
        a = max(1, color.alpha())
        self.markup_color_preview.setStyleSheet(
            f"background: rgba({color.red()},{color.green()},{color.blue()},{a}); border: 1px solid #666;"
        )

    def _add_layer(self):
        name, ok = QInputDialog.getText(self, "Add Layer", "Layer name:")
        if not ok or not str(name).strip():
            return
        if not self.image_canvas.add_layer(name):
            QMessageBox.warning(self, "Add Layer", "Could not add layer (name may already exist).")
        self._rebuild_layer_combo()
        self._refresh_layer_controls()

    def _rename_layer(self):
        current = self._current_layer_name()
        name, ok = QInputDialog.getText(self, "Rename Layer", "New name:", text=current)
        if not ok or not str(name).strip() or str(name).strip() == current:
            return
        if not self.image_canvas.rename_layer(current, name):
            QMessageBox.warning(self, "Rename Layer", "Could not rename layer.")
        self._rebuild_layer_combo()
        self._refresh_layer_controls()

    def _delete_layer(self):
        current = self._current_layer_name()
        confirm = QMessageBox.question(
            self,
            "Delete Layer",
            f"Delete layer '{current}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if not self.image_canvas.delete_layer(current):
            QMessageBox.warning(self, "Delete Layer", "Could not delete layer (at least one layer is required).")
        self._rebuild_layer_combo()
        self._refresh_layer_controls()

    def _duplicate_layer(self):
        current = self._current_layer_name()
        name, ok = QInputDialog.getText(self, "Duplicate Layer", "New layer name:", text=f"{current} Copy")
        if not ok or not str(name).strip():
            return
        if not self.image_canvas.duplicate_layer(current, name):
            QMessageBox.warning(self, "Duplicate Layer", "Could not duplicate layer.")
        self._rebuild_layer_combo()
        self._refresh_layer_controls()

    def _toggle_layer_lock(self):
        layer = self._current_layer_name()
        state = self.image_canvas.get_layer_state(layer)
        self.image_canvas.set_layer_locked(layer, not bool(state.get("locked", False)))
        self.image_canvas._schedule_autosave()
        self._rebuild_layer_combo()
        self._refresh_layer_controls()

    def _on_layer_list_item_changed(self, item):
        """Handle layer list item text/check-state changes (e.g. inline rename)."""
        if item is None:
            return
        # Visibility toggling is handled by eventFilter; name changes are managed
        # by _rename_layer. This handler just ensures the canvas stays in sync.
        layer_name = item.text()
        if layer_name:
            self._refresh_layer_controls()

    def _save_lighting_prompt(self):
        """Persist the lighting prompt text for the active layer."""
        layer = self._current_layer_name()
        if not layer:
            return
        text = self.lighting_prompt_edit.text()
        self.image_canvas.set_layer_lighting_prompt(layer, text)
        self.image_canvas._schedule_autosave()

    def _cancel_relight_job(self):
        self._relight_cancelled = True
        if self._relight_progress:
            self._relight_progress.setLabelText("Cancelling... waiting for current step")

    def _on_relight_completed(self, success, message, result_bgr):
        if self._relight_progress:
            self._relight_progress.close()
            self._relight_progress = None

        worker = self._relight_worker
        self._relight_worker = None
        if worker is not None:
            worker.deleteLater()

        if self._relight_cancelled:
            self._relight_cancelled = False
            return

        if not success or result_bgr is None:
            QMessageBox.warning(self, "Lighting Prompt", message)
            return

        ok, msg = self.image_canvas.apply_lighting_result(
            self._relight_target_layer,
            self._relight_prompt_text,
            result_bgr,
        )
        if not ok:
            QMessageBox.warning(self, "Lighting Prompt", msg)

    def _rebuild_layer_combo(self):
        current = self.image_canvas.active_layer
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        for name in self.image_canvas.layer_order:
            state = self.image_canvas.get_layer_state(name)
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setIcon(self._make_eye_icon(bool(state.get("visible", True))))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.layer_list.addItem(item)
        for i in range(self.layer_list.count()):
            it = self.layer_list.item(i)
            if it and self._layer_name_from_item(it) == current:
                self.layer_list.setCurrentRow(i)
                break
        if self.layer_list.currentRow() < 0 and self.layer_list.count() > 0:
            self.layer_list.setCurrentRow(0)
        self.layer_list.blockSignals(False)

    def eventFilter(self, obj, event):
        if hasattr(self, "layer_list") and obj is self.layer_list.viewport() and event.type() == QEvent.Type.MouseMove:
            item = self.layer_list.itemAt(event.pos())
            if item is not None:
                rect = self.layer_list.visualItemRect(item)
                rel_x = int(event.pos().x() - rect.x())
                if 0 <= rel_x <= 34:
                    self.layer_list.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                else:
                    self.layer_list.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            else:
                self.layer_list.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            return False

        if hasattr(self, "layer_list") and obj is self.layer_list.viewport() and event.type() == QEvent.Type.Leave:
            self.layer_list.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            return False

        if (
            hasattr(self, "layer_list")
            and obj is self.layer_list.viewport()
            and event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            item = self.layer_list.itemAt(event.pos())
            if item is not None:
                rect = self.layer_list.visualItemRect(item)
                rel_x = int(event.pos().x() - rect.x())
                layer = self._layer_name_from_item(item)
                # Photoshop-style: click the eye icon lane to toggle visibility.
                if 0 <= rel_x <= 34:
                    state = self.image_canvas.get_layer_state(layer)
                    self.image_canvas.set_layer_visible(layer, not bool(state.get("visible", True)))
                    self.image_canvas._schedule_autosave()
                    self.layer_list.setCurrentItem(item)
                    self._refresh_layer_controls()
                    return True
        return super().eventFilter(obj, event)

    def _layer_name_from_item(self, item):
        if item is None:
            return self.image_canvas.active_layer
        stored = item.data(Qt.ItemDataRole.UserRole)
        if stored:
            return str(stored)
        return item.text()

    def _make_layer_thumbnail_icon(self, layer_name, state):
        layer_img = self.image_canvas.annotation_layers.get(layer_name)
        base = self.image_canvas.base_pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        thumb_w, thumb_h = 44, 44
        thumb = QImage(thumb_w, thumb_h, QImage.Format.Format_ARGB32_Premultiplied)
        thumb.fill(QColor(30, 30, 30, 255))
        p = QPainter(thumb)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.drawImage(QRect(0, 0, thumb_w, thumb_h), base)
        if layer_img is not None and not layer_img.isNull():
            p.setOpacity(0.95)
            p.drawImage(QRect(0, 0, thumb_w, thumb_h), layer_img)
        border = QColor(220, 170, 60) if bool(state.get("locked", False)) else QColor(90, 90, 90)
        p.setPen(QPen(border, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(1, 1, thumb_w - 2, thumb_h - 2)
        eye_pm = self._make_eye_icon(bool(state.get("visible", True))).pixmap(12, 12)
        lock_pm = self._make_lock_icon(bool(state.get("locked", False))).pixmap(12, 12)
        p.drawPixmap(3, 3, eye_pm)
        p.drawPixmap(18, 3, lock_pm)
        p.end()
        return QIcon(QPixmap.fromImage(thumb))

    def _make_eye_icon(self, visible):
        pm = QPixmap(16, 16)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        col = QColor(220, 220, 220) if visible else QColor(130, 130, 130)
        p.setPen(QPen(col, 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(2, 5, 12, 6)
        if visible:
            p.setBrush(col)
            p.drawEllipse(7, 7, 2, 2)
        else:
            p.drawLine(3, 13, 13, 3)
        p.end()
        return QIcon(pm)

    def _make_lock_icon(self, locked):
        pm = QPixmap(16, 16)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        col = QColor(230, 200, 110) if locked else QColor(130, 130, 130)
        p.setPen(QPen(col, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(4, 7, 8, 6)
        if locked:
            p.drawArc(4, 2, 8, 8, 0 * 16, 180 * 16)
        else:
            p.drawArc(7, 2, 8, 8, 40 * 16, 140 * 16)
        p.end()
        return QIcon(pm)

    def _current_layer_name(self):
        if not hasattr(self, "layer_list"):
            return self.image_canvas.active_layer
        item = self.layer_list.currentItem()
        if item:
            return self._layer_name_from_item(item)
        return self.image_canvas.active_layer

    def _refresh_layer_controls(self):
        layer = self._current_layer_name()
        state = self.image_canvas.get_layer_state(layer)

        # Keep list checkbox state in sync when layer settings change externally.
        self.layer_list.blockSignals(True)
        for i in range(self.layer_list.count()):
            it = self.layer_list.item(i)
            if it and self._layer_name_from_item(it) == layer:
                it.setText(layer)
                it.setIcon(self._make_eye_icon(bool(state.get("visible", True))))
                break
        self.layer_list.blockSignals(False)

        opacity = int(state.get("opacity", 100))
        self.layer_opacity_slider.blockSignals(True)
        self.layer_opacity_slider.setValue(opacity)
        self.layer_opacity_slider.blockSignals(False)
        self.layer_opacity_label.setText(f"{opacity}%")

        blend = str(state.get("blend", "normal")).lower()
        idx = self.layer_blend_combo.findText(blend)
        self.layer_blend_combo.blockSignals(True)
        if idx >= 0:
            self.layer_blend_combo.setCurrentIndex(idx)
        self.layer_blend_combo.blockSignals(False)

        if not hasattr(self, 'lighting_prompt_edit'):
            return
        self.lighting_prompt_edit.blockSignals(True)
        self.lighting_prompt_edit.setText(self.image_canvas.get_layer_lighting_prompt(layer))
        self.lighting_prompt_edit.blockSignals(False)

        locked = bool(state.get("locked", False))
        self.layer_lock_btn.setText("Unlock Layer" if locked else "Lock Layer")

    def _on_layer_list_current_changed(self, current, _previous):
        if current is None:
            return
        self.image_canvas.set_active_layer(self._layer_name_from_item(current))
        self._refresh_layer_controls()

    def _on_layer_opacity_changed(self, value):
        layer = self._current_layer_name()
        self.layer_opacity_label.setText(f"{int(value)}%")
        self.image_canvas.set_layer_opacity(layer, int(value))
        self.image_canvas._schedule_autosave()

    def _on_layer_blend_changed(self, blend):
        layer = self._current_layer_name()
        self.image_canvas.set_layer_blend_mode(layer, blend)
        self.image_canvas._schedule_autosave()

    def _move_active_layer(self, direction):
        self.image_canvas.move_active_layer(direction)
        self._rebuild_layer_combo()
        self._refresh_layer_controls()
        self.image_canvas._schedule_autosave()

    def _set_tool_mode(self, mode):
        self._ensure_editable_active_layer()
        self.select_toggle.blockSignals(True)
        self.select_toggle.setChecked(False)
        self.select_toggle.blockSignals(False)
        self.draw_toggle.blockSignals(True)
        self.draw_toggle.setChecked(True)
        self.draw_toggle.blockSignals(False)
        self.image_canvas.set_drawing_enabled(True)
        self.image_canvas.set_tool_mode(mode)

    def _ensure_editable_active_layer(self):
        layer = self._current_layer_name()
        state = self.image_canvas.get_layer_state(layer)
        changed = False
        if not bool(state.get("visible", True)):
            self.image_canvas.set_layer_visible(layer, True)
            changed = True
        if bool(state.get("locked", False)):
            self.image_canvas.set_layer_locked(layer, False)
            changed = True
        if changed:
            self.image_canvas._schedule_autosave()
            self._rebuild_layer_combo()
            self._refresh_layer_controls()

    def _on_select_toggled(self, enabled):
        self.image_canvas.set_drawing_enabled(not enabled)
        self.image_canvas.set_tool_mode("select" if enabled else "pen")
        if enabled:
            self.draw_toggle.blockSignals(True)
            self.draw_toggle.setChecked(False)
            self.draw_toggle.blockSignals(False)

    def _set_shape_tool(self, mode, enabled, source_btn=None):
        if not enabled:
            if self.image_canvas.tool_mode == mode:
                self.image_canvas.set_tool_mode("pen")
            return
        all_tool_buttons = (
            self.circle_btn,
            self.arrow_btn,
            self.text_btn,
            self.blemish_brush_btn,
            self.blur_brush_btn,
            self.clone_stamp_btn,
            self.eraser_toggle,
        )
        for btn in all_tool_buttons:
            if btn is not source_btn:
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
        self._set_tool_mode(mode)

    def load_compare_image(self):
        base = Path(self.filepath)
        default = base.with_name(f"{base.stem}_edited{base.suffix}")
        if not default.exists():
            default = base
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Load Edited Output",
            str(default),
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not chosen:
            return
        pix = QPixmap(chosen)
        if pix.isNull():
            QMessageBox.warning(self, "Invalid Image", "Could not load selected image.")
            return
        self.compare_path = chosen
        self.image_canvas.set_compare_pixmap(pix)
        self.compare_toggle.setChecked(True)

    def _save_project(self):
        """Save all layers, annotations, settings, and notes to a JSON project file."""
        base_path = Path(self.filepath)
        default_proj = base_path.with_name(f"{base_path.stem}_project.json")
        chosen, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            str(default_proj),
            "Project Files (*.json)"
        )
        if not chosen:
            return
        try:
            proj = {
                "layers": self.image_canvas.layer_order,
                "layer_settings": self.image_canvas.layer_settings,
                "vector_annotations": self.image_canvas.vector_annotations,
                "notes": self.notes_edit.toPlainText() if hasattr(self, "notes_edit") else "",
            }
            Path(chosen).write_text(json.dumps(proj, indent=2), encoding="utf-8")
            QMessageBox.information(self, "Project Saved", f"Project saved to {Path(chosen).name}")
        except Exception as e:
            QMessageBox.warning(self, "Save Project Error", f"Failed to save project: {e}")

    def _load_project(self):
        """Load all layers, annotations, settings, and notes from a JSON project file."""
        base_path = Path(self.filepath)
        default_proj = base_path.with_name(f"{base_path.stem}_project.json")
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Load Project",
            str(default_proj.parent),
            "Project Files (*.json)"
        )
        if not chosen:
            return
        try:
            proj = json.loads(Path(chosen).read_text(encoding="utf-8"))
            if isinstance(proj, dict):
                if isinstance(proj.get("layer_settings"), dict):
                    self.image_canvas.layer_settings = proj["layer_settings"]
                if isinstance(proj.get("vector_annotations"), list):
                    self.image_canvas.vector_annotations = proj["vector_annotations"]
                if proj.get("notes"):
                    self.notes_edit.setPlainText(proj["notes"])
                self.image_canvas.update()
                self._rebuild_layer_combo()
                self._refresh_layer_controls()
                QMessageBox.information(self, "Project Loaded", "Project loaded successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Load Project Error", f"Failed to load project: {e}")

    def _autosave_project_state(self):
        """Periodically save project state for recovery."""
        base_path = Path(self.filepath)
        autosave = base_path.with_name(f"{base_path.stem}_autosave.json")
        try:
            proj = {
                "layers": self.image_canvas.layer_order,
                "layer_settings": self.image_canvas.layer_settings,
                "vector_annotations": self.image_canvas.vector_annotations,
                "notes": self.notes_edit.toPlainText() if hasattr(self, "notes_edit") else "",
            }
            autosave.write_text(json.dumps(proj, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _try_load_autosave_project(self):
        """Attempt to load autosave recovery state on project open."""
        base_path = Path(self.filepath)
        autosave = base_path.with_name(f"{base_path.stem}_autosave.json")
        if autosave.exists():
            try:
                proj = json.loads(autosave.read_text(encoding="utf-8"))
                if isinstance(proj, dict):
                    if isinstance(proj.get("layer_settings"), dict):
                        self.image_canvas.layer_settings = proj["layer_settings"]
                    if isinstance(proj.get("vector_annotations"), list):
                        self.image_canvas.vector_annotations = proj["vector_annotations"]
                    if proj.get("notes") and hasattr(self, "notes_edit"):
                        self.notes_edit.setPlainText(proj["notes"])
                    self.image_canvas.update()
                    self._rebuild_layer_combo()
                    self._refresh_layer_controls()
            except Exception:
                pass

    def _on_compare_toggled(self, enabled):
        if enabled and (self.image_canvas.compare_pixmap is None or self.image_canvas.compare_pixmap.isNull()):
            self.load_compare_image()
            if self.image_canvas.compare_pixmap is None or self.image_canvas.compare_pixmap.isNull():
                self.compare_toggle.blockSignals(True)
                self.compare_toggle.setChecked(False)
                self.compare_toggle.blockSignals(False)
                self.image_canvas.set_compare_enabled(False)
                return
        self.image_canvas.set_compare_enabled(enabled)

    def _on_compare_mode_changed(self, label):
        mode_map = {"Split": "split", "Before": "before", "After": "after"}
        self.image_canvas.set_compare_mode(mode_map.get(label, "split"))
        self.compare_split_btn.setChecked(label == "Split")
        self.compare_before_btn.setChecked(label == "Before")
        self.compare_after_btn.setChecked(label == "After")

    def _cycle_compare_mode(self):
        labels = ["Split", "Before", "After"]
        current = self.compare_mode_combo.currentText()
        try:
            idx = labels.index(current)
        except ValueError:
            idx = 0
        self.compare_mode_combo.setCurrentText(labels[(idx + 1) % len(labels)])

    def _on_zoom_changed(self, scale_factor):
        self.zoom_label.setText(f"{int(scale_factor * 100)}%")

    def _on_draw_toggled(self, enabled):
        if enabled:
            self._ensure_editable_active_layer()
        self.image_canvas.set_drawing_enabled(enabled)
        if enabled and self.select_toggle.isChecked():
            self.select_toggle.blockSignals(True)
            self.select_toggle.setChecked(False)
            self.select_toggle.blockSignals(False)
        if enabled and self.image_canvas.tool_mode not in ("eraser", "circle", "arrow", "text"):
            self.image_canvas.set_tool_mode("pen")

    def _set_unsaved_image_changes(self, has_changes):
        self._unsaved_image_changes = bool(has_changes)
        self.save_image_btn.setEnabled(self._unsaved_image_changes)
        self.unsaved_label.setVisible(self._unsaved_image_changes)

    def _refresh_retouch_compare_view(self):
        if self._retouch_result_pixmap is not None and not self._retouch_result_pixmap.isNull():
            self.image_canvas.set_compare_pixmap(self._retouch_result_pixmap)
            self.image_canvas.set_compare_ratio(0.5)
            self.compare_toggle.blockSignals(True)
            self.compare_toggle.setChecked(True)
            self.compare_toggle.blockSignals(False)
            self.image_canvas.set_compare_enabled(True)
            self._set_unsaved_image_changes(True)
            self.undo_retouch_btn.setEnabled(len(self._retouch_history) > 1)
        else:
            self.image_canvas.set_compare_enabled(False)
            self.compare_toggle.blockSignals(True)
            self.compare_toggle.setChecked(False)
            self.compare_toggle.blockSignals(False)
            self.undo_retouch_btn.setEnabled(False)

    def undo_retouch(self):
        if len(self._retouch_history) <= 1:
            return
        self._retouch_history.pop()
        prev = self._retouch_history[-1]
        self._retouch_result_pixmap = prev.copy() if prev is not None else None
        self._refresh_retouch_compare_view()

    def _current_image_source_path(self):
        if self._retouch_result_pixmap is not None and not self._retouch_result_pixmap.isNull():
            temp_src = self.annotation_dir / f"{self.photo_id:06d}_working_source.png"
            temp_src.parent.mkdir(parents=True, exist_ok=True)
            self._retouch_result_pixmap.save(str(temp_src), "PNG")
            return str(temp_src)

        if not self._unsaved_image_changes:
            return self.filepath

        # Persist current in-memory image to a temp source for subsequent retouch passes.
        temp_src = self.annotation_dir / f"{self.photo_id:06d}_working_source.png"
        temp_src.parent.mkdir(parents=True, exist_ok=True)
        self.image_canvas.base_pixmap.save(str(temp_src), "PNG")
        return str(temp_src)

    def apply_ai_retouch(self):
        """Apply OpenCV inpainting to remove blemishes marked by circle annotations."""
        annotations = self.image_canvas.vector_annotations
        blemish_circles = [a for a in annotations if a.get("type") == "circle" and a.get("layer") == "blemish"]
        
        if not blemish_circles:
            QMessageBox.information(
                self,
                "No Blemishes Marked",
                "No blemish circles found. Use the Circle tool on the 'blemish' layer to mark areas for removal."
            )
            return
        
        retoucher = ImageRetoucher()

        source_path = self._current_image_source_path()
        output_path = self.annotation_dir / f"{self.photo_id:06d}_retouch_preview.png"
        algorithm = self.retouch_algo_combo.currentText()
        radius = int(self.retouch_radius_spin.value())
        padding = int(self.retouch_padding_spin.value())
        self._last_retouch_settings = {"algorithm": algorithm, "radius": radius, "padding": padding}
        
        # Show progress
        progress = QProgressDialog("Applying AI retouch...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()
        
        success, final_path, message = retoucher.apply_blemish_removal(
            source_path,
            annotations,
            output_path=output_path,
            algorithm=algorithm,
            inpaint_radius=radius,
            mask_padding=padding,
        )
        
        progress.close()
        
        if success:
            new_pixmap = QPixmap(final_path)
            if new_pixmap.isNull():
                QMessageBox.warning(self, "Retouch Failed", "Retouch completed but preview image could not be loaded.")
                return

            # Keep original as base image and use retouched result for compare.
            self._retouch_result_pixmap = new_pixmap

            if not self._retouch_history:
                self._retouch_history.append(None)
            self._retouch_history.append(new_pixmap.copy())
            self._refresh_retouch_compare_view()

            QMessageBox.information(
                self,
                "Retouch Applied",
                f"{message}\n\nCompare is active with a draggable divider. Use 'Undo Retouch' to step back."
            )
        else:
            QMessageBox.warning(self, "Retouch Failed", message)

    def save_current_image(self):
        """Save the current on-screen image changes using Save/Copy/Cancel options."""
        if not self._unsaved_image_changes:
            QMessageBox.information(self, "No Changes", "There are no unsaved image changes.")
            return

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Save Image")
        dialog.setText("How would you like to save this image?")
        dialog.setInformativeText("Save overwrites the original file. Copy creates a new file.")
        save_btn = dialog.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        copy_btn = dialog.addButton("Copy", QMessageBox.ButtonRole.ActionRole)
        cancel_btn = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(save_btn)
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked == cancel_btn:
            return

        pixmap_to_save = self._retouch_result_pixmap if self._retouch_result_pixmap is not None else self.image_canvas.base_pixmap

        if clicked == save_btn:
            backup_path = None
            if self.parent() and hasattr(self.parent(), "cache_dir"):
                backup_dir = Path("data") / "retouch_backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_path = backup_dir / f"photo_{int(self.photo_id):06d}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{Path(self.filepath).suffix}"
                try:
                    shutil.copy2(self.filepath, backup_path)
                except Exception:
                    backup_path = None

            ok = pixmap_to_save.save(self.filepath)
            if ok:
                if self.parent() and hasattr(self.parent(), "_append_retouch_audit"):
                    self.parent()._append_retouch_audit({
                        "operation": "retouch",
                        "mode": "overwrite",
                        "photo_id": int(self.photo_id),
                        "source_path": self.filepath,
                        "output_path": self.filepath,
                        "backup_path": str(backup_path) if backup_path else None,
                        "settings": dict(self._last_retouch_settings),
                    })
                if self.parent() and hasattr(self.parent(), "refresh_photos"):
                    self.parent().refresh_photos()
                if self.parent() and hasattr(self.parent(), "refresh_gallery"):
                    self.parent().refresh_gallery()
                self._set_unsaved_image_changes(False)
                self._retouch_result_pixmap = None
                self.image_canvas.set_compare_enabled(False)
                self.compare_toggle.blockSignals(True)
                self.compare_toggle.setChecked(False)
                self.compare_toggle.blockSignals(False)
                self.image_canvas.base_pixmap = QPixmap(self.filepath)
                self.image_canvas.update()
                QMessageBox.information(self, "Saved", f"Image saved over original:\n{self.filepath}")
            else:
                QMessageBox.warning(self, "Save Failed", "Could not overwrite the original image.")
            return

        if clicked == copy_btn:
            base = Path(self.filepath)
            default_name = f"{base.stem}_retouched{base.suffix}"
            out_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Image Copy",
                str(base.with_name(default_name)),
                "Images (*.png *.jpg *.jpeg *.bmp)"
            )
            if not out_path:
                return
            ok = pixmap_to_save.save(out_path)
            if ok:
                if self.parent() and hasattr(self.parent(), "db"):
                    source_photo = self.parent().db.get_photo(self.photo_id)
                    if source_photo:
                        metadata = self.parent()._clone_photo_metadata_for_copy(source_photo)
                        self.parent().db.add_photo(out_path, metadata)
                if self.parent() and hasattr(self.parent(), "_append_retouch_audit"):
                    self.parent()._append_retouch_audit({
                        "operation": "retouch",
                        "mode": "copy",
                        "photo_id": int(self.photo_id),
                        "source_path": self.filepath,
                        "output_path": out_path,
                        "backup_path": None,
                        "settings": dict(self._last_retouch_settings),
                    })
                if self.parent() and hasattr(self.parent(), "refresh_photos"):
                    self.parent().refresh_photos()
                if self.parent() and hasattr(self.parent(), "refresh_gallery"):
                    self.parent().refresh_gallery()
                self._set_unsaved_image_changes(False)
                self._retouch_result_pixmap = None
                QMessageBox.information(self, "Saved", f"Image copy saved to:\n{out_path}")
            else:
                QMessageBox.warning(self, "Save Failed", "Could not save image copy.")

    def export_marked_copy(self):
        base = Path(self.filepath)
        default_name = f"{base.stem}_marked{base.suffix}"
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Marked Copy",
            str(base.with_name(default_name)),
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not out_path:
            return

        ok = self.image_canvas.export_marked_copy(out_path)
        if ok:
            QMessageBox.information(self, "Export Complete", f"Saved marked copy to:\n{out_path}")
        else:
            QMessageBox.warning(self, "Export Failed", "Could not export marked copy.")

    def showEvent(self, event):
        super().showEvent(event)
        if not self._did_initial_fit:
            # Start zoomed out so large images are fully manageable at open.
            QTimer.singleShot(0, self.image_canvas.fit_to_view)
            self._did_initial_fit = True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.image_canvas.set_space_pan_enabled(True)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.image_canvas.set_space_pan_enabled(False)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def closeEvent(self, event):
        if self._unsaved_image_changes:
            decision = QMessageBox.question(
                self,
                "Unsaved Image Changes",
                "You have unsaved image changes. Save before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if decision == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if decision == QMessageBox.StandardButton.Yes:
                self.save_current_image()
                if self._unsaved_image_changes:
                    # Save cancelled or failed.
                    event.ignore()
                    return

        self.save_notes()
        self.image_canvas.save_annotations()
        super().closeEvent(event)

    def _load_notes(self):
        try:
            photo = self.db.get_photo(self.photo_id)
            if photo:
                raw_notes = photo.get('notes') or ''
                cleaned_notes = self._strip_checklist_block(raw_notes)
                self.notes_edit.blockSignals(True)
                self.notes_edit.setPlainText(cleaned_notes)
                self.notes_edit.blockSignals(False)

                # Prefer dedicated checklist sidecar state; fallback to legacy notes block.
                if not self._load_checklist_state():
                    self._load_checklist_from_notes(raw_notes)

                # Migrate legacy notes by removing embedded checklist text.
                if raw_notes != cleaned_notes:
                    self.db.update_photo_metadata(self.photo_id, {'notes': cleaned_notes})
        except Exception as e:
            print(f"load_notes error: {e}")

    def _on_checklist_changed(self, _item):
        self._save_timer.stop()
        self._save_timer.start(400)

    def _collect_checklist_lines(self):
        lines = []
        for i in range(self.retouch_checklist.count()):
            item = self.retouch_checklist.item(i)
            status = "x" if item.checkState() == Qt.CheckState.Checked else " "
            lines.append(f"[{status}] {item.text()}")
        return lines

    def _merge_notes_and_checklist(self):
        base_text = self.notes_edit.toPlainText()
        marker = "\n\nRetouch Checklist:\n"
        if marker in base_text:
            base_text = base_text.split(marker)[0].rstrip()
        checklist_block = marker + "\n".join(self._collect_checklist_lines())
        return (base_text + checklist_block).strip()

    def _checklist_state_path(self):
        return self.annotation_dir / f"{self.photo_id:06d}_retouch_checklist.json"

    def _strip_checklist_block(self, notes_text):
        marker = "\n\nRetouch Checklist:\n"
        if marker in notes_text:
            return notes_text.split(marker)[0].rstrip()
        marker2 = "Retouch Checklist:"
        if marker2 in notes_text:
            return notes_text.split(marker2, 1)[0].rstrip()
        return notes_text

    def _save_checklist_state(self):
        try:
            self.annotation_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "items": [
                    {
                        "text": self.retouch_checklist.item(i).text(),
                        "checked": self.retouch_checklist.item(i).checkState() == Qt.CheckState.Checked,
                    }
                    for i in range(self.retouch_checklist.count())
                ]
            }
            self._checklist_state_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return True
        except Exception as e:
            print(f"save checklist state error: {e}")
            return False

    def _load_checklist_state(self):
        p = self._checklist_state_path()
        if not p.exists():
            return False
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            items = data.get("items", []) if isinstance(data, dict) else []
            state_map = {str(it.get("text", "")): bool(it.get("checked", False)) for it in items if isinstance(it, dict)}
            self.retouch_checklist.blockSignals(True)
            for i in range(self.retouch_checklist.count()):
                item = self.retouch_checklist.item(i)
                if item.text() in state_map:
                    item.setCheckState(Qt.CheckState.Checked if state_map[item.text()] else Qt.CheckState.Unchecked)
            self.retouch_checklist.blockSignals(False)
            return True
        except Exception as e:
            print(f"load checklist state error: {e}")
            return False

    def _load_checklist_from_notes(self, notes_text):
        marker = "Retouch Checklist:"
        if marker not in notes_text:
            return
        block = notes_text.split(marker, 1)[1]
        parsed = {}
        for raw in block.splitlines():
            line = raw.strip()
            if not line.startswith("[") or "]" not in line:
                continue
            state = line[1:2].lower() == "x"
            text = line.split("]", 1)[1].strip()
            if text:
                parsed[text] = state

        for i in range(self.retouch_checklist.count()):
            item = self.retouch_checklist.item(i)
            if item.text() in parsed:
                item.setCheckState(Qt.CheckState.Checked if parsed[item.text()] else Qt.CheckState.Unchecked)

    def export_task_list(self):
        export_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Retouch Task List",
            f"photo_{self.photo_id:06d}_retouch_tasks.txt",
            "Text Files (*.txt)"
        )
        if not export_path:
            return

        lines = [
            f"Photo ID: {self.photo_id:06d}",
            f"File: {self.filepath}",
            "",
            "Retouch Tasks:",
        ] + self._collect_checklist_lines()

        try:
            with open(export_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            QMessageBox.information(self, "Exported", f"Task list saved to:\n{export_path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", str(e))

    def _on_notes_changed(self):
        self._save_timer.stop()
        self._save_timer.start(1000)

    def save_notes(self):
        try:
            text = self.notes_edit.toPlainText()
            self.db.update_photo_metadata(self.photo_id, {'notes': text})
            self._save_checklist_state()

            if self.parent() and hasattr(self.parent(), 'refresh_photo_row'):
                self.parent().refresh_photo_row(self.photo_id)

            if self.parent() and hasattr(self.parent(), 'statusBar') and self.parent().statusBar():
                self.parent().statusBar().showMessage("Notes saved", 1000)
        except Exception as e:
            print(f"save_notes error: {e}")



class AnalyzerThread(QThread):
    """Background thread for analyzing images"""
    progress = pyqtSignal(int, int, str)  # current, total, filename
    photo_analyzed = pyqtSignal(dict)  # photo data
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, folder_path, include_subfolders, db_path):
        super().__init__()
        self.folder_path = folder_path
        self.include_subfolders = include_subfolders
        self.db_path = db_path  # Store path instead of connection
        self._is_running = True

    def run(self):
        """Analyze all images in the folder"""
        db = PhotoDatabase(self.db_path)

        try:
            # Get all image files (including raw, HEIC, WEBP for modern cameras)
            image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp',
                                '.webp', '.tiff', '.tif', '.heic', '.heif',
                                '.raw', '.cr2', '.nef', '.arw')

            if self.include_subfolders:
                files = []
                for ext in image_extensions:
                    files.extend(Path(self.folder_path).rglob(f'*{ext}'))
                    files.extend(Path(self.folder_path).rglob(f'*{ext.upper()}'))
            else:
                files = []
                for ext in image_extensions:
                    files.extend(Path(self.folder_path).glob(f'*{ext}'))
                    files.extend(Path(self.folder_path).glob(f'*{ext.upper()}'))

            # Deduplicate (case-insensitive) to avoid double-counting on case-insensitive FS
            seen: set = set()
            deduped = []
            for f in files:
                key = str(f).lower()
                if key not in seen:
                    seen.add(key)
                    deduped.append(f)
            files = deduped

            total = len(files)
            
            start_time = time.time()

            for i, filepath in enumerate(files):
                if not self._is_running:
                    break
                
                filepath = str(filepath)
                filename = Path(filepath).name
                
                # Calculate ETA
                if i > 0:
                    elapsed = time.time() - start_time
                    avg_time = elapsed / i
                    remaining = (total - i) * avg_time
                    eta_mins = int(remaining / 60)
                    eta_secs = int(remaining % 60)
                    status = f"{filename} (ETA: {eta_mins}m {eta_secs}s)"
                else:
                    status = filename
                
                self.progress.emit(i + 1, total, status)
                
                try:
                    # Check if already analyzed
                    existing = db.get_photo_by_path(filepath)
                    if existing and existing.get('scene_type'):
                        continue  # Skip already analyzed

                    # EXIF extraction
                    try:
                        from core.exif_extractor import extract_exif
                        exif_meta = extract_exif(filepath)
                    except Exception:
                        exif_meta = {}

                    # Quality scoring
                    try:
                        from core.quality_scorer import score_image
                        quality_meta = score_image(filepath)
                    except Exception:
                        quality_meta = {}

                    # Perceptual hash (for duplicate detection)
                    try:
                        from core.duplicate_detector import perceptual_hash, md5_hash
                        p_hash = perceptual_hash(filepath)
                        f_hash = md5_hash(filepath)
                    except Exception:
                        p_hash = ''
                        f_hash = ''

                    # Analyze image with AI
                    metadata = analyze_image(filepath, db)

                    # Merge EXIF, quality, and hash data (non-destructive: AI fields take priority)
                    for k, v in exif_meta.items():
                        if k not in metadata:
                            metadata[k] = v
                    for k in ('blur_score', 'exposure_score', 'quality', 'quality_issues'):
                        if k in quality_meta:
                            metadata[k] = quality_meta[k]
                    if 'blur_score' in quality_meta:
                        metadata['quality_score'] = quality_meta['blur_score']
                    if p_hash:
                        metadata['perceptual_hash'] = p_hash
                    if f_hash:
                        metadata['file_hash'] = f_hash

                    # Add or update in database
                    if existing:
                        # Protect user corrections
                        corrected_fields = db.get_corrected_fields_for_photo(existing['id'])
                        if corrected_fields:
                            for field in corrected_fields:
                                if field in metadata:
                                    del metadata[field]

                        if metadata:
                            db.update_photo_metadata(existing['id'], metadata)
                        photo_id = existing['id']
                    else:
                        photo_id = db.add_photo(filepath, metadata)

                    # Get complete photo data and emit
                    photo_data = db.get_photo(photo_id)
                    self.photo_analyzed.emit(photo_data)

                except Exception as e:
                    self.error.emit(f"Error analyzing {filename}: {str(e)}")
            
            self.finished.emit()
        
        except Exception as e:
            self.error.emit(str(e))
        finally:
            db.close()

    def stop(self):
        """Stop the analyzer thread"""
        self._is_running = False


class ReanalyzerThread(QThread):
    """Background thread for re-analyzing selected photos"""
    progress = pyqtSignal(int, int, str)  # current, total, status
    finished = pyqtSignal()
    error = pyqtSignal(str)
    photo_analyzed = pyqtSignal(dict)  # photo data (for compatibility)
    
    def __init__(self, photos_to_analyze, db_path):
        super().__init__()
        self.photos_to_analyze = photos_to_analyze
        self.db_path = db_path
        self._is_running = True
        # Add attributes for compatibility with shared handlers
        self.folder_path = None
        self.include_subfolders = False
    
    def run(self):
        """Re-analyze photos in background"""
        db = PhotoDatabase(self.db_path)
        
        try:
            start_time = time.time()
            total = len(self.photos_to_analyze)
            
            for i, photo in enumerate(self.photos_to_analyze):
                if not self._is_running:
                    break
                
                # Calculate ETA
                filename = photo.get('filename') or 'Unknown'
                filepath = photo.get('filepath')
                
                if not filepath:
                    self.error.emit(f"Photo has no filepath: {photo.get('id')}")
                    continue
                
                if i > 0:
                    elapsed = time.time() - start_time
                    avg_time = elapsed / i
                    remaining = (total - i) * avg_time
                    eta_mins = int(remaining / 60)
                    eta_secs = int(remaining % 60)
                    status = f"{filename} (ETA: {eta_mins}m {eta_secs}s)"
                else:
                    status = filename
                
                self.progress.emit(i + 1, total, status)
                
                try:
                    # Re-analyze with AI
                    metadata = analyze_image(filepath, db)
                    
                    # Get fields that user has manually corrected
                    corrected_fields = db.get_corrected_fields_for_photo(photo['id'])
                    
                    # Preserve user corrections
                    if corrected_fields:
                        for field in corrected_fields:
                            if field in metadata:
                                del metadata[field]
                    
                    # Update database
                    if metadata:
                        db.update_photo_metadata(photo['id'], metadata)
                
                except Exception as e:
                    self.error.emit(f"Error analyzing {filename}: {str(e)}")
            
            self.finished.emit()
        
        except Exception as e:
            self.error.emit(str(e))
        finally:
            db.close()
    
    def stop(self):
        """Stop the reanalyzer thread"""
        self._is_running = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhotoFlow")
        self.resize(1200, 800)
        self.setMinimumSize(400, 300)
        from PyQt6.QtCore import QSize, QSettings
        self.icon_size = QSize(24, 24)
        self.settings = QSettings()
        self.analyzer_thread = None
        self._live_gallery_update_count = 0
        self.db = PhotoDatabase()
        self.cache_dir = Path("thumbnail_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.retouch_audit_path = Path("data") / "retouch_audit.jsonl"
        self.retouch_audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.batch_retouch_settings = {"algorithm": "telea", "radius": 3, "padding": 2}
        self.init_ui()
    # Library tab column indices - UPDATE THIS MAPPING IF COLUMNS CHANGE
    COL_CHECKBOX = 0
    COL_ID = 1
    COL_THUMBNAIL = 2
    COL_SCENE = 3
    COL_MOOD = 4
    COL_SUBJECTS = 5
    COL_LOCATION = 6
    COL_OBJECTS = 7
    COL_STATUS = 8
    COL_IG = 9
    COL_TIKTOK = 10
    COL_PACKAGE = 11
    COL_TAGS = 12
    COL_DATE = 13
    COL_FILEPATH = 14
    COL_NOTES = 15

    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        # Top section - Folder selection and analysis
        top_section = self.create_top_section()
        main_layout.addWidget(top_section)
        # Tab widget for different views
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)   # allow tab bar to scroll when window is narrow
        self.tabs.tabBar().setExpanding(False)  # don't stretch tabs to fill bar width
        try:
            self.gallery_tab = GalleryTab(self)
            self.tabs.addTab(self.gallery_tab, "Gallery")
        except Exception as e:
            print(f'Error creating Gallery tab: {e}', file=sys.stderr)
        try:
            self.photos_tab = PhotosTab(self)
            self.tabs.addTab(self.photos_tab, "Library")
            self.photo_table = self.photos_tab.photo_table
            self.persistent_selected_ids = self.photos_tab.persistent_selected_ids
        except Exception as e:
            print(f'Error creating Library tab: {e}', file=sys.stderr)
        try:
            self.filters_tab = FiltersTab(self)
            self.tabs.addTab(self.filters_tab, "Filters")
        except Exception as e:
            print(f'Error creating Filters tab: {e}', file=sys.stderr)
        try:
            self.publish_tab = PublishTab(self)
            self.tabs.addTab(self.publish_tab, "Publish")
        except Exception as e:
            print(f'Error creating Publish tab: {e}', file=sys.stderr)
        try:
            self.instagram_tab = InstagramTab(self)
            self.tabs.addTab(self.instagram_tab, "Instagram")
        except Exception as e:
            print(f'Error creating Instagram tab: {e}', file=sys.stderr)
        try:
            self.tiktok_tab = TikTokTab(self)
            self.tabs.addTab(self.tiktok_tab, "TikTok")
        except Exception as e:
            print(f'Error creating TikTok tab: {e}', file=sys.stderr)
        try:
            self.albums_tab = AlbumsTab(self)
            self.tabs.addTab(self.albums_tab, "Albums")
        except Exception as e:
            print(f'Error creating Albums tab: {e}', file=sys.stderr)
        try:
            self.composer_tab = ComposerTab(self)
            self.tabs.addTab(self.composer_tab, "Compose")
        except Exception as e:
            print(f'Error creating Composer tab: {e}', file=sys.stderr)
        try:
            self.schedule_tab = ScheduleTab(self)
            self.tabs.addTab(self.schedule_tab, "Schedule")
        except Exception as e:
            print(f'Error creating Schedule tab: {e}', file=sys.stderr)
        try:
            self.duplicates_tab = DuplicatesTab(self)
            self.tabs.addTab(self.duplicates_tab, "Duplicates")
        except Exception as e:
            print(f'Error creating Duplicates tab: {e}', file=sys.stderr)
        try:
            self.batch_tab = BatchTab(self)
            self.tabs.addTab(self.batch_tab, "Batch")
        except Exception as e:
            print(f'Error creating Batch tab: {e}', file=sys.stderr)
        try:
            self.history_tab = HistoryTab(self)
            self.tabs.addTab(self.history_tab, "History")
        except Exception as e:
            print(f'Error creating History tab: {e}', file=sys.stderr)
        try:
            self.settings_tab = SettingsTab(self)
            self.tabs.addTab(self.settings_tab, "Settings")
        except Exception as e:
            print(f'Error creating Settings tab: {e}', file=sys.stderr)
        try:
            self.learning_tab = AILearningTab(self)
            self.tabs.addTab(self.learning_tab, "AI Learning")
        except Exception as e:
            print(f'Error creating AI Learning tab: {e}', file=sys.stderr)
        try:
            self.vocabularies_tab = VocabulariesTab(self)
            self.tabs.addTab(self.vocabularies_tab, "Vocabularies")
        except Exception as e:
            print(f'Error creating Vocabularies tab: {e}', file=sys.stderr)
        try:
            self.face_matching_tab = FaceMatchingTab(self)
            self.tabs.addTab(self.face_matching_tab, "Face Match")
        except Exception as e:
            print(f'Error creating Face Match tab: {e}', file=sys.stderr)

        main_layout.addWidget(self.tabs)
        
        # Tag cloud at bottom
        tag_cloud_widget = self.create_tag_cloud()
        main_layout.addWidget(tag_cloud_widget)
        
        self.tabs.setCurrentIndex(0)

        # Start post scheduler background worker
        try:
            from core.social.scheduler import SchedulerWorker
            def _get_creds(platform):
                return self.db.get_credentials(platform) or {}
            self._scheduler_worker = SchedulerWorker(self.db.db_path, _get_creds)
            def _on_post_sent(post):
                if self.statusBar():
                    self.statusBar().showMessage(
                        f"Scheduled post sent to {post.get('platform', '?')}!", 5000
                    )
                if hasattr(self, 'schedule_tab'):
                    self.schedule_tab.refresh()

            def _on_post_failed(post, err):
                if self.statusBar():
                    self.statusBar().showMessage(
                        f"Scheduled post failed ({post.get('platform', '?')}): {err}", 8000
                    )
                if hasattr(self, 'schedule_tab'):
                    self.schedule_tab.refresh()

            self._scheduler_worker.post_sent.connect(_on_post_sent)
            self._scheduler_worker.post_failed.connect(_on_post_failed)
            self._scheduler_worker.start()
            print('Scheduler worker started', file=sys.stderr)
        except Exception as e:
            print(f'Scheduler worker error: {e}', file=sys.stderr)

        # Ensure gallery is populated on startup without requiring manual refresh.
        try:
            if hasattr(self, 'gallery_tab') and self.gallery_tab:
                self.gallery_tab.refresh()
        except Exception as e:
            print(f"initial gallery refresh error: {e}")

    def _append_retouch_audit(self, entry):
        """Append a JSONL audit record for retouch operations."""
        try:
            payload = dict(entry)
            payload["timestamp"] = datetime.utcnow().isoformat() + "Z"
            with open(self.retouch_audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=True) + "\n")
        except Exception as e:
            print(f"retouch audit append error: {e}")

    def set_batch_retouch_settings(self, settings):
        """Update batch retouch settings from popup controls."""
        try:
            self.batch_retouch_settings = {
                "algorithm": str(settings.get("algorithm", "telea")).lower(),
                "radius": int(settings.get("radius", 3)),
                "padding": int(settings.get("padding", 2)),
            }
            if self.statusBar():
                s = self.batch_retouch_settings
                self.statusBar().showMessage(
                    f"Batch retouch settings synced: {s['algorithm']}, radius {s['radius']}, padding {s['padding']}",
                    3500,
                )
            if hasattr(self, 'photos_tab') and self.photos_tab and hasattr(self.photos_tab, '_refresh_batch_settings_label'):
                self.photos_tab._refresh_batch_settings_label()
        except Exception as e:
            print(f"set_batch_retouch_settings error: {e}")

    def get_batch_retouch_settings_label(self):
        """Readable summary for library toolbar label."""
        s = dict(getattr(self, "batch_retouch_settings", {"algorithm": "telea", "radius": 3, "padding": 2}))
        return f"Batch: {s.get('algorithm', 'telea')} r{s.get('radius', 3)} p{s.get('padding', 2)}"

    def apply_batch_retouch_preset(self, preset_name):
        """Apply a named preset to batch retouch settings from the Library tab."""
        presets = {
            "subtle": {"algorithm": "telea", "radius": 2, "padding": 1},
            "balanced": {"algorithm": "telea", "radius": 3, "padding": 2},
            "strong": {"algorithm": "ns", "radius": 5, "padding": 3},
        }
        cfg = presets.get(preset_name)
        if not cfg:
            return
        self.set_batch_retouch_settings(cfg)

    def _read_retouch_audit(self):
        """Read retouch audit JSONL records."""
        entries = []
        if not self.retouch_audit_path.exists():
            return entries
        try:
            with open(self.retouch_audit_path, "r", encoding="utf-8") as f:
                for line in f:
                    text = line.strip()
                    if not text:
                        continue
                    try:
                        entries.append(json.loads(text))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"retouch audit read error: {e}")
        return entries

    def open_retouch_history_dialog(self):
        """Open a dialog showing retouch audit history with revert support."""
        entries = self._read_retouch_audit()
        if not entries:
            QMessageBox.information(self, "Retouch History", "No retouch history found yet.")
            return

        rows = list(reversed(entries[-300:]))

        dialog = QDialog(self)
        dialog.setWindowTitle("Retouch History")
        dialog.resize(1160, 620)
        layout = QVBoxLayout(dialog)

        hint = QLabel("Select a row and click 'Revert Selected' for overwrite retouch entries.")
        hint.setStyleSheet("color: #c8c8c8;")
        layout.addWidget(hint)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Photo ID:"))
        photo_id_filter = QLineEdit()
        photo_id_filter.setPlaceholderText("e.g. 123")
        photo_id_filter.setMaximumWidth(120)
        filter_row.addWidget(photo_id_filter)

        filter_row.addWidget(QLabel("Mode:"))
        mode_filter = QComboBox()
        mode_filter.addItems(["Any", "overwrite", "copy", "-"])
        mode_filter.setMaximumWidth(120)
        filter_row.addWidget(mode_filter)

        filter_row.addWidget(QLabel("Find:"))
        text_filter = QLineEdit()
        text_filter.setPlaceholderText("Search path, operation, or note text")
        filter_row.addWidget(text_filter)

        filter_row.addWidget(QLabel("From:"))
        from_filter = QLineEdit()
        from_filter.setPlaceholderText("YYYY-MM-DD")
        from_filter.setMaximumWidth(120)
        filter_row.addWidget(from_filter)

        filter_row.addWidget(QLabel("To:"))
        to_filter = QLineEdit()
        to_filter.setPlaceholderText("YYYY-MM-DD")
        to_filter.setMaximumWidth(120)
        filter_row.addWidget(to_filter)
        layout.addLayout(filter_row)

        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(["Time", "Operation", "Mode", "Photo ID", "Source", "Output", "Backup", "Note"])
        table.setRowCount(0)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(table)

        actions = QHBoxLayout()
        revert_btn = QPushButton("Revert Selected")
        revert_btn.setIcon(_icon('revert'))
        revert_btn.setIconSize(QSize(16, 16))
        close_btn = QPushButton("Close")
        close_btn.setIcon(_icon('close'))
        close_btn.setIconSize(QSize(16, 16))
        actions.addWidget(revert_btn)
        actions.addStretch()
        actions.addWidget(close_btn)
        layout.addLayout(actions)

        filtered_rows = []

        def _refresh_table_rows():
            filtered_rows.clear()

            id_text = photo_id_filter.text().strip()
            wanted_id = None
            if id_text:
                try:
                    wanted_id = int(id_text)
                except ValueError:
                    wanted_id = -1

            wanted_mode = mode_filter.currentText().strip().lower()
            if wanted_mode == "any":
                wanted_mode = None

            needle = text_filter.text().strip().lower()

            from_date = None
            to_date = None
            from_text = from_filter.text().strip()
            to_text = to_filter.text().strip()
            if from_text:
                try:
                    from_date = datetime.strptime(from_text, "%Y-%m-%d").date()
                except ValueError:
                    from_date = "invalid"
            if to_text:
                try:
                    to_date = datetime.strptime(to_text, "%Y-%m-%d").date()
                except ValueError:
                    to_date = "invalid"

            for entry in rows:
                pid = entry.get("photo_id")
                mode = str(entry.get("mode", "")).strip().lower()
                ts = str(entry.get("timestamp", "")).strip()

                if from_date == "invalid" or to_date == "invalid":
                    continue

                if from_date or to_date:
                    entry_date = None
                    try:
                        entry_date = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
                    except Exception:
                        try:
                            entry_date = datetime.strptime(ts[:10], "%Y-%m-%d").date()
                        except Exception:
                            entry_date = None
                    if entry_date is None:
                        continue
                    if from_date and entry_date < from_date:
                        continue
                    if to_date and entry_date > to_date:
                        continue

                if wanted_id is not None:
                    try:
                        if int(pid) != wanted_id:
                            continue
                    except Exception:
                        continue

                if wanted_mode is not None and mode != wanted_mode:
                    continue

                if needle:
                    searchable = " ".join([
                        str(entry.get("operation", "")),
                        str(entry.get("mode", "")),
                        str(entry.get("photo_id", "")),
                        str(entry.get("source_path", "")),
                        str(entry.get("output_path", entry.get("target_path", ""))),
                        str(entry.get("backup_path", entry.get("source_backup", ""))),
                        str(entry.get("note", "")),
                    ]).lower()
                    if needle not in searchable:
                        continue

                filtered_rows.append(entry)

            table.setRowCount(len(filtered_rows))
            for r, entry in enumerate(filtered_rows):
                values = [
                    str(entry.get("timestamp", "")),
                    str(entry.get("operation", "")),
                    str(entry.get("mode", "")),
                    str(entry.get("photo_id", "")),
                    str(entry.get("source_path", "")),
                    str(entry.get("output_path", entry.get("target_path", ""))),
                    str(entry.get("backup_path", entry.get("source_backup", ""))),
                    str(entry.get("note", "")),
                ]
                for c, v in enumerate(values):
                    table.setItem(r, c, QTableWidgetItem(v))

        photo_id_filter.textChanged.connect(lambda _v: _refresh_table_rows())
        mode_filter.currentTextChanged.connect(lambda _v: _refresh_table_rows())
        text_filter.textChanged.connect(lambda _v: _refresh_table_rows())
        from_filter.textChanged.connect(lambda _v: _refresh_table_rows())
        to_filter.textChanged.connect(lambda _v: _refresh_table_rows())
        _refresh_table_rows()

        def on_revert_selected():
            row = table.currentRow()
            if row < 0 or row >= len(filtered_rows):
                QMessageBox.information(dialog, "Retouch History", "Select a row first.")
                return

            entry = filtered_rows[row]
            if entry.get("operation") != "retouch" or entry.get("mode") != "overwrite":
                QMessageBox.warning(dialog, "Not Revertible", "Only overwrite retouch entries can be reverted.")
                return

            backup_path = entry.get("backup_path")
            target_path = entry.get("output_path") or entry.get("source_path")
            if not backup_path or not os.path.exists(backup_path):
                QMessageBox.warning(dialog, "Missing Backup", "Backup file is missing for this entry.")
                return
            if not target_path:
                QMessageBox.warning(dialog, "Invalid Entry", "No target path found for this entry.")
                return

            confirm = QMessageBox.question(
                dialog,
                "Confirm Revert",
                f"Restore backup to:\n{target_path}\n\nThis will overwrite current file contents.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            try:
                shutil.copy2(backup_path, target_path)
                self._append_retouch_audit({
                    "operation": "revert",
                    "photo_id": int(entry.get("photo_id", 0) or 0),
                    "target_path": target_path,
                    "source_backup": backup_path,
                })
                self.refresh_photos()
                self.refresh_gallery()
                QMessageBox.information(dialog, "Reverted", "Selected entry reverted successfully.")
            except Exception as e:
                QMessageBox.warning(dialog, "Revert Failed", f"Could not revert: {e}")

        revert_btn.clicked.connect(on_revert_selected)
        close_btn.clicked.connect(dialog.accept)
        dialog.exec()

    def _clone_photo_metadata_for_copy(self, photo):
        """Create metadata dict suitable for add_photo for duplicated images."""
        if not photo:
            return {}
        excluded = {"id", "filepath", "filename", "date_added", "date_created"}
        metadata = {k: v for k, v in photo.items() if k not in excluded}
        return metadata

    def _next_copy_path(self, source_path, suffix="_retouched"):
        base = Path(source_path)
        candidate = base.with_name(f"{base.stem}{suffix}{base.suffix}")
        if not candidate.exists():
            return candidate
        n = 2
        while True:
            candidate = base.with_name(f"{base.stem}{suffix}_{n}{base.suffix}")
            if not candidate.exists():
                return candidate
            n += 1

    def _last_overwrite_backup_for_photo(self, photo_id):
        entries = self._read_retouch_audit()
        for entry in reversed(entries):
            if entry.get("operation") != "retouch":
                continue
            if entry.get("mode") != "overwrite":
                continue
            if int(entry.get("photo_id", -1)) != int(photo_id):
                continue
            backup_path = entry.get("backup_path")
            if backup_path and os.path.exists(backup_path):
                return entry
        return None

    def _show_test_retouch_preview_dialog(self, source_path, preview_path):
        """Show a side-by-side before/after preview for single-photo retouch."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Test 1 Photo Preview")
        dialog.resize(1100, 680)

        layout = QVBoxLayout(dialog)
        title = QLabel("Before / After Preview")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)

        img_row = QHBoxLayout()

        before_box = QVBoxLayout()
        before_box.addWidget(QLabel("Before"))
        before_label = QLabel()
        before_label.setMinimumSize(480, 520)
        before_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        before_label.setStyleSheet("background: #1f1f1f; border: 1px solid #444;")
        before_box.addWidget(before_label)
        img_row.addLayout(before_box)

        after_box = QVBoxLayout()
        after_box.addWidget(QLabel("After"))
        after_label = QLabel()
        after_label.setMinimumSize(480, 520)
        after_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        after_label.setStyleSheet("background: #1f1f1f; border: 1px solid #444;")
        after_box.addWidget(after_label)
        img_row.addLayout(after_box)

        layout.addLayout(img_row)

        src_pix = QPixmap(str(source_path))
        out_pix = QPixmap(str(preview_path))
        if not src_pix.isNull():
            before_label.setPixmap(src_pix.scaled(before_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        if not out_pix.isNull():
            after_label.setPixmap(out_pix.scaled(after_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        buttons = QHBoxLayout()
        buttons.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setIcon(_icon('save'))
        save_btn.setIconSize(QSize(16, 16))
        copy_btn = QPushButton("Copy")
        copy_btn.setIcon(_icon('copy'))
        copy_btn.setIconSize(QSize(16, 16))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setIcon(_icon('close'))
        cancel_btn.setIconSize(QSize(16, 16))
        buttons.addWidget(save_btn)
        buttons.addWidget(copy_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        choice = {"mode": "cancel"}

        def choose(mode):
            choice["mode"] = mode
            dialog.accept()

        save_btn.clicked.connect(lambda: choose("overwrite"))
        copy_btn.clicked.connect(lambda: choose("copy"))
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()
        return choice["mode"]

    def _run_batch_ai_retouch(self, target_ids, title, preview_mode=False):
        if not target_ids:
            QMessageBox.information(self, title, "Select or check one or more photos first.")
            return

        overwrite = False
        mode = None
        if not preview_mode:
            dialog = QMessageBox(self)
            dialog.setWindowTitle(title)
            dialog.setText(f"Run retouch for {len(target_ids)} selected photo(s)?")
            dialog.setInformativeText("Save overwrites originals. Copy creates duplicate files.")
            save_btn = dialog.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
            copy_btn = dialog.addButton("Copy", QMessageBox.ButtonRole.ActionRole)
            cancel_btn = dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            dialog.setDefaultButton(copy_btn)
            dialog.exec()

            clicked = dialog.clickedButton()
            if clicked == cancel_btn:
                return
            overwrite = clicked == save_btn
            mode = "overwrite" if overwrite else "copy"

        retoucher = ImageRetoucher()
        settings = dict(getattr(self, "batch_retouch_settings", {"algorithm": "telea", "radius": 3, "padding": 2}))
        settings["radius"] = max(1, int(settings.get("radius", 3)))
        settings["padding"] = max(0, int(settings.get("padding", 2)))
        done = 0
        skipped = 0
        failed = 0

        progress = QProgressDialog("Batch retouch in progress...", "Cancel", 0, len(target_ids), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        for i, photo_id in enumerate(target_ids, start=1):
            if progress.wasCanceled():
                break
            progress.setValue(i - 1)
            progress.setLabelText(f"Processing {i}/{len(target_ids)}")
            QApplication.processEvents()

            photo = self.db.get_photo(photo_id)
            if not photo or not photo.get("filepath") or not os.path.exists(photo.get("filepath")):
                skipped += 1
                continue

            vector_path = self.cache_dir / "annotations" / f"{int(photo_id):06d}_vector_annotations.json"
            if not vector_path.exists():
                skipped += 1
                continue

            try:
                annotations = json.loads(vector_path.read_text(encoding="utf-8"))
            except Exception:
                failed += 1
                continue

            blemish = [a for a in annotations if a.get("type") == "circle" and a.get("layer") == "blemish"]
            if not blemish:
                skipped += 1
                continue

            src_path = photo["filepath"]
            backup_path = None
            output = None
            ok = False
            message = ""

            if preview_mode:
                preview_dir = self.cache_dir / "annotations"
                preview_dir.mkdir(parents=True, exist_ok=True)
                preview_path = preview_dir / f"{int(photo_id):06d}_test_preview{Path(src_path).suffix}"

                ok, preview_output, message = retoucher.apply_blemish_removal(
                    src_path,
                    annotations,
                    output_path=preview_path,
                    algorithm=str(settings.get("algorithm", "telea")),
                    inpaint_radius=settings["radius"],
                    mask_padding=settings["padding"],
                )
                if not ok:
                    failed += 1
                    continue

                mode = self._show_test_retouch_preview_dialog(src_path, preview_output)
                if mode == "cancel":
                    skipped += 1
                    break

                overwrite = mode == "overwrite"
                if overwrite:
                    dst_path = src_path
                    backup_dir = Path("data") / "retouch_backups"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    backup_path = backup_dir / f"photo_{int(photo_id):06d}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{Path(src_path).suffix}"
                    try:
                        shutil.copy2(src_path, backup_path)
                        shutil.copy2(preview_output, dst_path)
                        ok = True
                        output = dst_path
                    except Exception:
                        failed += 1
                        continue
                else:
                    dst_path = str(self._next_copy_path(src_path))
                    try:
                        shutil.copy2(preview_output, dst_path)
                        ok = True
                        output = dst_path
                    except Exception:
                        failed += 1
                        continue
            else:
                if overwrite:
                    dst_path = src_path
                    backup_dir = Path("data") / "retouch_backups"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    backup_path = backup_dir / f"photo_{int(photo_id):06d}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{Path(src_path).suffix}"
                    try:
                        shutil.copy2(src_path, backup_path)
                    except Exception:
                        failed += 1
                        continue
                else:
                    dst_path = str(self._next_copy_path(src_path))

                ok, output, message = retoucher.apply_blemish_removal(
                    src_path,
                    annotations,
                    output_path=dst_path,
                    algorithm=str(settings.get("algorithm", "telea")),
                    inpaint_radius=settings["radius"],
                    mask_padding=settings["padding"],
                )
                if not ok:
                    failed += 1
                    continue

            if not overwrite and output:
                metadata = self._clone_photo_metadata_for_copy(photo)
                self.db.add_photo(output, metadata)

            self._append_retouch_audit({
                "operation": "retouch",
                "mode": mode,
                "photo_id": int(photo_id),
                "source_path": src_path,
                "output_path": output,
                "backup_path": str(backup_path) if backup_path else None,
                "settings": dict(settings),
                "note": message,
            })
            done += 1

        progress.setValue(len(target_ids))
        self.refresh_photos()
        self.refresh_gallery()
        QMessageBox.information(
            self,
            f"{title} Complete",
            f"Done: {done}\nSkipped: {skipped}\nFailed: {failed}"
        )

    def batch_ai_retouch_selected(self):
        """Apply AI blemish retouch to checked/selected photos in bulk."""
        target_ids = self.get_target_photo_ids()
        self._run_batch_ai_retouch(target_ids, "Batch Retouch", preview_mode=False)

    def batch_ai_retouch_test_one(self):
        """Apply AI retouch to only one checked/selected photo for quick validation."""
        target_ids = self.get_target_photo_ids()
        if target_ids:
            target_ids = [target_ids[0]]
        self._run_batch_ai_retouch(target_ids, "Test 1 Photo", preview_mode=True)

    def revert_last_retouch_selected(self):
        """Revert last overwrite retouch for checked/selected photos."""
        target_ids = self.get_target_photo_ids()
        if not target_ids:
            QMessageBox.information(self, "Revert Retouch", "Select or check one or more photos first.")
            return

        reverted = 0
        skipped = 0
        failed = 0

        for photo_id in target_ids:
            photo = self.db.get_photo(photo_id)
            if not photo or not photo.get("filepath"):
                skipped += 1
                continue
            last = self._last_overwrite_backup_for_photo(photo_id)
            if not last:
                skipped += 1
                continue
            backup_path = last.get("backup_path")
            if not backup_path or not os.path.exists(backup_path):
                skipped += 1
                continue
            try:
                shutil.copy2(backup_path, photo["filepath"])
                reverted += 1
                self._append_retouch_audit({
                    "operation": "revert",
                    "photo_id": int(photo_id),
                    "target_path": photo["filepath"],
                    "source_backup": backup_path,
                })
            except Exception:
                failed += 1

        self.refresh_photos()
        self.refresh_gallery()
        QMessageBox.information(
            self,
            "Revert Retouch Complete",
            f"Reverted: {reverted}\nSkipped: {skipped}\nFailed: {failed}"
        )

    def apply_theme(self, theme_name: str):
        """Apply the Default theme (base.qss + default.qss)."""
        try:
            base_dir = Path(__file__).parent
            theme_dir = base_dir / "themes"
            theme_map = {
                "Default": theme_dir / "default.qss",
            }
            base_qss_path = theme_dir / "base.qss"
            qss_parts = []
            # Always set Fusion style for consistency
            QApplication.instance().setStyle("Fusion")
            # Consistent font across themes
            QApplication.instance().setFont(QFont("Segoe UI", 10))
            # Load base QSS
            if base_qss_path.exists():
                with open(base_qss_path, "r", encoding="utf-8") as f:
                    qss_parts.append(f.read())
            # Load theme QSS
            qss_path = theme_map.get(theme_name, theme_map["Default"])
            if qss_path and qss_path.exists():
                with open(qss_path, "r", encoding="utf-8") as f:
                    qss_parts.append(f.read())
            # Apply combined stylesheet (or clear)
            QApplication.instance().setStyleSheet("\n".join(qss_parts))
        except Exception as e:
            print(f"apply_theme error: {e}")
    
    def _build_menus(self):
        """Build the application menu bar (View / Settings / Help)."""
        view_menu = self.menuBar().addMenu("&View")

        gallery_action = view_menu.addAction("Switch to &Gallery")
        gallery_action.setShortcut("Ctrl+1")
        gallery_action.triggered.connect(lambda: self.tabs.setCurrentIndex(0))

        library_action = view_menu.addAction("Switch to &Library")
        library_action.setShortcut("Ctrl+2")
        library_action.triggered.connect(lambda: self.tabs.setCurrentIndex(1))

        filters_action = view_menu.addAction("Switch to &Filters")
        filters_action.setShortcut("Ctrl+3")
        filters_action.triggered.connect(lambda: self.tabs.setCurrentIndex(2))

        view_menu.addSeparator()

        refresh_action = view_menu.addAction("&Refresh Photos")
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_photos)

        settings_menu = self.menuBar().addMenu("&Settings")
        prefs_action = settings_menu.addAction("&Preferences")
        prefs_action.setShortcut("Ctrl+,")
        prefs_action.triggered.connect(self.show_settings_dialog)

        help_menu = self.menuBar().addMenu("&Help")
        about_action = help_menu.addAction("&About PhotoFlow")
        about_action.triggered.connect(self.show_about_dialog)

    def show_about_dialog(self):
        """Show an About dialog"""
        QMessageBox.information(
            self,
            "About PhotoFlow",
            "PhotoFlow v2.0\n\n"
            "A desktop application for organizing photos and publishing to social media.\n\n"
            "Features:\n"
            "• AI-powered photo tagging and caption generation\n"
            "• Gallery and library views with albums\n"
            "• Multi-platform social media publishing\n"
            "• Post scheduling and queue management\n"
            "• Advanced filtering and batch operations\n\n"
            "© 2026 PhotoFlow"
        )
    
    def show_settings_dialog(self):
        """Show settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Preferences")
        dialog.setGeometry(300, 300, 500, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Thumbnail settings
        thumb_group = QGroupBox("Thumbnail Settings")
        thumb_layout = QVBoxLayout()
        
        thumb_layout.addWidget(QLabel("Default Gallery Thumbnail Size:"))
        gallery_size_combo = QComboBox()
        gallery_size_combo.addItems(["Small", "Medium", "Large"])
        gallery_size_combo.setCurrentText(self.gallery_tab.get_gallery_size())
        thumb_layout.addWidget(gallery_size_combo)
        
        thumb_group.setLayout(thumb_layout)
        layout.addWidget(thumb_group)
        
        # Theme settings
        theme_group = QGroupBox("Appearance")
        theme_layout = QVBoxLayout()
        theme_layout.addWidget(QLabel("UI Theme:"))
        theme_combo = QComboBox()
        theme_combo.addItems([
            "Default"
        ]) 
        # Default to Default if previous value isn’t available
        preferred = self.settings.value("ui_theme", "Default")
        if preferred in [theme_combo.itemText(i) for i in range(theme_combo.count())]:
            theme_combo.setCurrentText(preferred)
        else:
            theme_combo.setCurrentText("Default")
        theme_layout.addWidget(theme_combo)
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # Auto-save settings
        auto_save_group = QGroupBox("Auto-Save Settings")
        auto_save_layout = QVBoxLayout()
        
        auto_save_delay_label = QLabel("Notes Auto-Save Delay (ms):")
        auto_save_delay_spin = QSpinBox()
        auto_save_delay_spin.setMinimum(500)
        auto_save_delay_spin.setMaximum(5000)
        auto_save_delay_spin.setValue(1000)
        auto_save_delay_spin.setSingleStep(100)
        auto_save_layout.addWidget(auto_save_delay_label)
        auto_save_layout.addWidget(auto_save_delay_spin)
        
        auto_save_group.setLayout(auto_save_layout)
        layout.addWidget(auto_save_group)
        
        # Display settings
        display_group = QGroupBox("Display Settings")
        display_layout = QVBoxLayout()
        
        show_checkbox = QCheckBox("Show tips on startup")
        show_checkbox.setChecked(True)
        display_layout.addWidget(show_checkbox)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)
        
        # Info section
        info_group = QGroupBox("Database Information")
        info_layout = QVBoxLayout()
        
        db_path_label = QLabel(f"Database: {self.db.db_path}")
        db_path_label.setStyleSheet("color: gray; font-size: 9px;")
        info_layout.addWidget(db_path_label)
        
        cache_path_label = QLabel(f"Thumbnail Cache: {self.cache_dir}")
        cache_path_label.setStyleSheet("color: gray; font-size: 9px;")
        info_layout.addWidget(cache_path_label)
        
        clear_cache_btn = QPushButton("Clear Thumbnail Cache")
        clear_cache_btn.setIcon(_icon('trash'))
        clear_cache_btn.setIconSize(QSize(16, 16))
        clear_cache_btn.clicked.connect(self.clear_thumbnail_cache)
        info_layout.addWidget(clear_cache_btn)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.setIcon(_icon('check'))
        ok_btn.setIconSize(QSize(16, 16))
        ok_btn.clicked.connect(lambda: self.apply_settings(dialog, gallery_size_combo.currentText(), theme_combo.currentText()))
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setIcon(_icon('close'))
        cancel_btn.setIconSize(QSize(16, 16))
        cancel_btn.clicked.connect(dialog.close)
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.exec()
    
    def apply_settings(self, dialog, gallery_size, theme):
        """Apply settings and close dialog"""
        self.gallery_tab.set_gallery_size(gallery_size)
        self.settings.setValue("ui_theme", theme)
        self.apply_theme(theme)
        self.gallery_tab.refresh()
        dialog.close()
    
    def clear_thumbnail_cache(self):
        """Clear the thumbnail cache"""
        try:
            import shutil
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(exist_ok=True)
            QMessageBox.information(self, "Cache Cleared", "Thumbnail cache has been cleared.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to clear cache: {e}")
    
    def create_top_section(self):
        """Create the top section with folder selection"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Folder selection row
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Root Folder:"))
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Select root folder containing images...")
        self.folder_input.textChanged.connect(lambda text: self.save_last_folder(text) if text else None)
        folder_row.addWidget(self.folder_input)
        
        browse_btn = QPushButton("Browse")
        browse_btn.setIcon(_icon('folder'))
        browse_btn.setIconSize(QSize(16, 16))
        browse_btn.clicked.connect(self.browse_folder)
        folder_row.addWidget(browse_btn)

        relink_btn = QPushButton("Relink Paths")
        relink_btn.setIcon(_icon('link_external'))
        relink_btn.setIconSize(QSize(16, 16))
        relink_btn.setToolTip("Update stored file paths to the selected root folder")
        relink_btn.clicked.connect(self.relink_filepaths)
        folder_row.addWidget(relink_btn)
        
        layout.addLayout(folder_row)

        # Restore last folder selection and start watcher
        last_folder = self.settings.value("last_folder", "")
        if last_folder:
            self.folder_input.setText(last_folder)
            # Defer watcher start until after the full UI is built
            QTimer.singleShot(500, lambda: self._start_folder_watcher(last_folder) if last_folder and os.path.exists(last_folder) else None)
        
        # Options row
        options_row = QHBoxLayout()
        self.subfolder_checkbox = QCheckBox("Include Subfolders")
        self.subfolder_checkbox.setChecked(True)
        options_row.addWidget(self.subfolder_checkbox)
        options_row.addStretch()
        
        self.analyze_btn = QPushButton("Analyze Images")
        self.analyze_btn.setIcon(_icon('sparkle'))
        self.analyze_btn.setIconSize(QSize(16, 16))
        self.analyze_btn.clicked.connect(self.start_analysis)
        options_row.addWidget(self.analyze_btn)
        
        self.cancel_btn = QPushButton("Cancel Analysis")
        self.cancel_btn.setIcon(_icon('stop'))
        self.cancel_btn.setIconSize(QSize(16, 16))
        self.cancel_btn.clicked.connect(self.cancel_analysis)
        self.cancel_btn.setEnabled(False)
        options_row.addWidget(self.cancel_btn)
        
        layout.addLayout(options_row)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self._build_menus()
        return widget

    def create_photos_tab(self):
        """Return the shared photos tab widget."""
        return self.photos_tab

    def create_publish_tab(self):
        """Return the shared publish tab widget."""
        return self.publish_tab
    
    def create_instagram_tab(self):
        """Return the shared Instagram tab widget."""
        return self.instagram_tab
    
    def create_tiktok_tab(self):
        """Return the shared TikTok tab widget."""
        return self.tiktok_tab
    
    def post_to_tiktok(self):
        """Post to TikTok"""
        if not hasattr(self, 'tt_selected_media_id'):
            QMessageBox.warning(self, "Error", "Please select media first")
            return

        caption = self.tt_caption_edit.toPlainText()
        hashtags = self.tt_hashtags_edit.text()
        full_caption = f"{caption}\n{hashtags}".strip()

        if len(full_caption) > 2200:
            QMessageBox.warning(self, "Error", f"Caption too long: {len(full_caption)}/2200 characters")
            return

        try:
            if not self.db.has_api_credentials('tiktok'):
                QMessageBox.warning(self, 'Not Connected', 'Connect your TikTok account in Settings first.')
                return
            creds = self.db.get_api_credentials('tiktok')
            from core.social.tiktok_api import TikTokAPI
            api = TikTokAPI(creds)
            photo = self.db.get_photo(self.tt_selected_media_id)
            if not photo:
                QMessageBox.warning(self, 'Error', 'Photo not found in library.')
                return
            ok, msg = api.post_photo(photo['filepath'], full_caption)
            if ok:
                QMessageBox.information(self, 'Posted', f'Posted to TikTok!\n{msg}')
                self.statusBar().showMessage('TikTok post sent', 3000)
            else:
                QMessageBox.warning(self, 'Post Failed', msg)
        except ImportError:
            QMessageBox.information(
                self, 'TikTok API Not Available',
                'Direct TikTok posting requires the TikTok API module.\n'
                'Use the TikTok tab to manage posts.'
            )
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to post: {e}')

    def create_tag_cloud(self):
        """Create tag cloud widget at bottom of app"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        widget.setMaximumHeight(120)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Header with title and refresh button
        header = QHBoxLayout()
        title = QLabel("<b>Tags</b>")
        header.addWidget(title)
        
        header.addStretch()
        
        # Clear filter button
        self.clear_tag_filter_btn = QPushButton("Clear Filter")
        self.clear_tag_filter_btn.clicked.connect(self.clear_tag_filter)
        self.clear_tag_filter_btn.setVisible(False)
        header.addWidget(self.clear_tag_filter_btn)
        
        # Refresh button
        refresh_tags_btn = QPushButton("Refresh Tags")
        refresh_tags_btn.clicked.connect(self.refresh_tag_cloud)
        header.addWidget(refresh_tags_btn)
        
        layout.addLayout(header)
        
        # Scroll area for tags
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Container for tag buttons
        self.tag_cloud_container = QWidget()
        self.tag_cloud_layout = QHBoxLayout(self.tag_cloud_container)
        self.tag_cloud_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        scroll.setWidget(self.tag_cloud_container)
        layout.addWidget(scroll)
        
        # Track currently active tags
        self.active_tags = set()
        self.tag_buttons = {}  # Store tag buttons for styling updates
        
        return widget
    
    def create_gallery_tab(self):
        """Return the shared gallery tab widget."""
        return self.gallery_tab

    def get_photo_id_from_row(self, row: int) -> int:
        """Safely extract photo ID from table row using COL_ID constant"""
        try:
            id_item = self.photo_table.item(row, self.COL_ID)
            if id_item:
                return int(id_item.text())
        except (ValueError, AttributeError):
            pass
        return None

    def on_row_checkbox_toggled(self, state: int):
        """Handle toggling of the persistent selection checkbox widgets."""
        try:
            sender = self.sender()
            if not sender:
                return
            photo_id = sender.property('photo_id')
            if photo_id is None:
                return
            if state == Qt.CheckState.Checked.value:
                self.persistent_selected_ids.add(int(photo_id))
            else:
                self.persistent_selected_ids.discard(int(photo_id))
        except Exception as e:
            print(f"Checkbox toggle error: {e}")

    def get_checked_photo_ids(self) -> set:
        """Return a set of photo IDs that are checked in the checkbox column."""
        if hasattr(self, 'persistent_selected_ids'):
            return set(self.persistent_selected_ids)
        if hasattr(self, 'photos_tab') and hasattr(self.photos_tab, 'persistent_selected_ids'):
            return set(self.photos_tab.persistent_selected_ids)
        return set()

    def get_selected_photo_ids(self) -> set:
        """Return a set of photo IDs based on current table selection (fallback)."""
        rows = {it.row() for it in self.photo_table.selectedItems()} if self.photo_table.selectedItems() else set()
        ids = set()
        for r in rows:
            pid = self.get_photo_id_from_row(r)
            if pid is not None:
                ids.add(pid)
        return ids

    def get_target_photo_ids(self) -> list:
        """Prefer checked IDs; otherwise use selected IDs. Returns a list for stable iteration."""
        checked = self.get_checked_photo_ids()
        if checked:
            return list(checked)
        return list(self.get_selected_photo_ids())

    def map_photo_ids_to_rows(self, photo_ids: set) -> dict:
        """Build a mapping from photo_id to current table row index for the given IDs."""
        id_to_row = {}
        if not photo_ids:
            return id_to_row
        row_count = self.photo_table.rowCount()
        for r in range(row_count):
            pid = self.get_photo_id_from_row(r)
            if pid in photo_ids:
                id_to_row[pid] = r
                if len(id_to_row) == len(photo_ids):
                    break
        return id_to_row

    def debug_log_cell_click(self, row: int, col: int):
        """Verbose logging for a clicked cell: row, column, header, constants, and content."""
        try:
            header_item = self.photo_table.horizontalHeaderItem(col)
            header = header_item.text() if header_item else "<no header>"
            pid = self.get_photo_id_from_row(row)

            # Map constant name for the column
            col_constants = {
                self.COL_CHECKBOX: 'COL_CHECKBOX',
                self.COL_ID: 'COL_ID',
                self.COL_THUMBNAIL: 'COL_THUMBNAIL',
                self.COL_SCENE: 'COL_SCENE',
                self.COL_MOOD: 'COL_MOOD',
                self.COL_SUBJECTS: 'COL_SUBJECTS',
                self.COL_LOCATION: 'COL_LOCATION',
                self.COL_OBJECTS: 'COL_OBJECTS',
                self.COL_STATUS: 'COL_STATUS',
                self.COL_IG: 'COL_IG',
                self.COL_TIKTOK: 'COL_TIKTOK',
                self.COL_PACKAGE: 'COL_PACKAGE',
                self.COL_TAGS: 'COL_TAGS',
                self.COL_DATE: 'COL_DATE',
                self.COL_FILEPATH: 'COL_FILEPATH'
            }
            col_const_name = col_constants.get(col, '<no-const>')

            # Determine item vs widget content
            item = self.photo_table.item(row, col)
            widget = self.photo_table.cellWidget(row, col)
            item_text = item.text() if item else '<no item>'
            widget_info = '<no widget>'
            if widget:
                # Try to pull checkbox state if present
                cb = None
                lay = widget.layout() if hasattr(widget, 'layout') else None
                if lay and lay.count():
                    maybe = lay.itemAt(0).widget()
                    if isinstance(maybe, QCheckBox):
                        cb = maybe
                if cb:
                    widget_info = f"QCheckBox(checked={cb.isChecked()}, photo_id={cb.property('photo_id')})"
                else:
                    widget_info = widget.__class__.__name__

            # Field mapping if applicable
            mapped_field = self.COLUMN_TO_FIELD.get(col, '<no field>')

            print("[CellClick] row=", row, "col=", col, "header=", header,
                  "const=", col_const_name, "photo_id=", pid,
                  "item=", item_text, "widget=", widget_info, "field=", mapped_field)
            if self.statusBar():
                self.statusBar().showMessage(f"Clicked r{row} c{col} [{header}] -> {col_const_name}", 3000)
        except Exception as e:
            print(f"debug_log_cell_click error: {e}")

    # Notes pane on main UI removed; no row-click notes loader

    def eventFilter(self, obj, event):
        """Handle middle-click on thumbnail to open file location and swallow the event."""
        try:
            # Check if photos_tab exists and has photo_table
            if not hasattr(self, 'photos_tab') or not hasattr(self.photos_tab, 'photo_table'):
                return super().eventFilter(obj, event)
            
            if obj is self.photos_tab.photo_table.viewport() and event.type() in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
            ):
                if event.button() == Qt.MouseButton.MiddleButton:
                    idx = self.photos_tab.photo_table.indexAt(event.pos())
                    if idx.isValid() and idx.column() == self.photos_tab.COL_THUMBNAIL:
                        row = idx.row()
                        fp_item = self.photos_tab.photo_table.item(row, self.photos_tab.COL_FILEPATH)
                        if fp_item:
                            path = fp_item.text()
                            folder = os.path.dirname(path)
                            if folder and os.path.isdir(folder):
                                os.startfile(folder)
                                event.accept()
                                return True  # handled, stop propagation to thumbnail widget
        except Exception as e:
            print(f"eventFilter error: {e}")
        return super().eventFilter(obj, event)
    
    def get_icon(self, filename: str, label: str = "") -> QIcon:
        """Load an icon from icons folder; fallback to colored placeholder with label"""
        try:
            icon_path = Path("icons") / filename
            if icon_path.exists():
                return QIcon(str(icon_path))
            # Fallback placeholder
            size = 20
            pm = QPixmap(size, size)
            pm.fill(QColor(90, 110, 130))
            painter = QPainter(pm)
            painter.setPen(Qt.GlobalColor.white)
            font = QFont()
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, label[:2])
            painter.end()
            return QIcon(pm)
        except Exception as e:
            print(f"Icon load error for {filename}: {e}")
            return QIcon()

    def sanitize_folder_name(self, name: str) -> str:
        """Return a filesystem-safe folder name"""
        return ''.join(ch for ch in (name or '').strip() if ch.isalnum() or ch in (' ', '-', '_')).strip() or 'package'

    def toggle_staged(self, platform: str):
        """Move checked/selected photos to staged/<platform>/<package> and update filepaths"""
        target_ids = set(self.get_target_photo_ids())
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check photos to stage (or select cells)")
            return
        id_to_row = self.map_photo_ids_to_rows(target_ids)
        root = self.folder_input.text().strip()
        if not root:
            QMessageBox.warning(self, "No Root Folder", "Please set the root folder at the top and try again.")
            return
        moved = 0
        for photo_id in target_ids:
            row = id_to_row.get(photo_id)
            photo = self.db.get_photo(photo_id)
            if not photo or not photo.get('filepath'):
                continue
            pkg_list = self.db.get_packages(photo_id)
            pkg = self.sanitize_folder_name(pkg_list[0]) if pkg_list else self.sanitize_folder_name(photo.get('package_name') or '')
            dest_dir = os.path.join(root, 'staged', platform, pkg)
            os.makedirs(dest_dir, exist_ok=True)
            filename = os.path.basename(photo['filepath'])
            dest_path = os.path.join(dest_dir, filename)
            try:
                if os.path.abspath(photo['filepath']) != os.path.abspath(dest_path):
                    shutil.move(photo['filepath'], dest_path)
                # Update DB and table
                self.db.update_photo_metadata(photo_id, {'filepath': dest_path})
                if row is not None:
                    self.photo_table.item(row, self.COL_FILEPATH).setText(dest_path)
                moved += 1
            except Exception as e:
                print(f"Stage move error for {photo_id}: {e}")
        self.statusBar().showMessage(f"Staged {moved} photo(s) to {platform}", 3000)

    def move_to_released(self, photo_id: int, platform: str):
        """Move a single photo to released/<platform>/<package> and update filepath"""
        root = self.folder_input.text().strip()
        photo = self.db.get_photo(photo_id)
        if not root or not photo or not photo.get('filepath'):
            return False
        pkg_list = self.db.get_packages(photo_id)
        pkg = self.sanitize_folder_name(pkg_list[0]) if pkg_list else self.sanitize_folder_name(photo.get('package_name') or '')
        dest_dir = os.path.join(root, 'released', platform.replace('released_', ''), pkg)
        os.makedirs(dest_dir, exist_ok=True)
        filename = os.path.basename(photo['filepath'])
        dest_path = os.path.join(dest_dir, filename)
        try:
            if os.path.abspath(photo['filepath']) != os.path.abspath(dest_path):
                shutil.move(photo['filepath'], dest_path)
            self.db.update_photo_metadata(photo_id, {'filepath': dest_path})
            return dest_path
        except Exception as e:
            print(f"Release move error for {photo_id}: {e}")
            return False

    def unstage_selected(self):
        """Move checked/selected photos back to root/<package> by stripping staged/<platform>/ from path"""
        target_ids = set(self.get_target_photo_ids())
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check photos to unstage (or select cells)")
            return
        id_to_row = self.map_photo_ids_to_rows(target_ids)
        root = self.folder_input.text().strip()
        if not root:
            QMessageBox.warning(self, "No Root Folder", "Please set the root folder at the top and try again.")
            return
        moved = 0
        root_path = Path(root)
        for photo_id in target_ids:
            row = id_to_row.get(photo_id)
            photo = self.db.get_photo(photo_id)
            if not photo or not photo.get('filepath'):
                continue

            src_path = Path(photo['filepath'])
            dest_path = None
            try:
                rel = src_path.relative_to(root_path)
                if len(rel.parts) >= 3 and rel.parts[0] == 'staged':
                    # Drop 'staged/<platform>' and keep the remaining relative path
                    dest_path = root_path.joinpath(*rel.parts[2:])
            except ValueError:
                pass
            if dest_path is None:
                dest_path = src_path  # fallback: leave in place

            dest_dir = dest_path.parent
            os.makedirs(dest_dir, exist_ok=True)

            try:
                if src_path.resolve() != dest_path.resolve():
                    shutil.move(str(src_path), str(dest_path))
                self.db.update_photo_metadata(photo_id, {'filepath': str(dest_path)})
                if row is not None:
                    self.photo_table.item(row, self.COL_FILEPATH).setText(str(dest_path))
                moved += 1
            except Exception as e:
                print(f"Unstage move error for {photo_id}: {e}")
        self.statusBar().showMessage(f"Unstaged {moved} photo(s) to root", 3000)

    def unpackage_selected(self):
        """Clear package name and move checked/selected photos to root directory"""
        target_ids = set(self.get_target_photo_ids())
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check photos to unpackage (or select cells)")
            return
        id_to_row = self.map_photo_ids_to_rows(target_ids)
        root = self.folder_input.text().strip()
        if not root:
            QMessageBox.warning(self, "No Root Folder", "Please set the root folder at the top and try again.")
            return
        moved = 0
        for photo_id in target_ids:
            row = id_to_row.get(photo_id)
            photo = self.db.get_photo(photo_id)
            if not photo or not photo.get('filepath'):
                continue
            filename = os.path.basename(photo['filepath'])
            dest_dir = root
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, filename)
            try:
                if os.path.abspath(photo['filepath']) != os.path.abspath(dest_path):
                    shutil.move(photo['filepath'], dest_path)
                # Clear packages and update DB + table
                self.db.set_packages(photo_id, [])
                self.db.update_photo_metadata(photo_id, {'filepath': dest_path})
                if row is not None:
                    self.photo_table.item(row, self.COL_PACKAGE).setText('')
                    self.photo_table.item(row, self.COL_FILEPATH).setText(dest_path)
                moved += 1
            except Exception as e:
                print(f"Unpackage move error for {photo_id}: {e}")
        self.statusBar().showMessage(f"Unpackaged {moved} photo(s) to root and cleared package", 3000)

    def on_table_cell_double_clicked(self, row: int, col: int):
        """Delegate to PhotosTab."""
        if hasattr(self, 'photos_tab') and self.photos_tab:
            self.photos_tab.on_table_cell_double_clicked(row, col)

    def refresh_learning_data(self):
        """Refresh the AI learning data display — delegates to AILearningTab."""
        if hasattr(self, 'learning_tab'):
            self.learning_tab.refresh_learning_data()
    
    def clear_learning_data(self):
        """Clear all AI learning data"""
        # First backup before clearing
        backup_success = self.backup_learning_data()
        
        # Strong warning dialog
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("⚠️ Clear All AI Learning Data?")
        msg.setText("<b>WARNING: This will delete ALL AI learning data!</b>")
        msg.setInformativeText(
            "This action will:\n"
            "• Delete all correction patterns\n"
            "• Reset AI learning to zero\n"
            f"• A backup {'was created' if backup_success else 'FAILED'}\n\n"
            "Are you absolutely sure you want to continue?"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        
        reply = msg.exec()
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.db.clear_ai_corrections():
                    self.refresh_learning_data()
                    self.statusBar().showMessage("Learning data cleared (backup created)", 3000)
                else:
                    QMessageBox.critical(self, "Error", "Failed to clear learning data")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear learning data: {e}")
    
    def backup_learning_data(self) -> bool:
        """Quick internal backup — called automatically before a clear/restore."""
        import os
        data_dir = os.path.join(os.path.dirname(self.db.db_path), '')
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(data_dir, f'ai_corrections_backup_{ts}.json')
        return self.db.export_ai_corrections_json(path)

    def manual_backup_learning_data(self):
        """Backup learning data to a user-chosen JSON file."""
        from PyQt6.QtWidgets import QFileDialog
        import os
        default_name = f"ai_corrections_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data_dir = os.path.dirname(self.db.db_path)
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save Learning Data Backup', os.path.join(data_dir, default_name),
            'JSON files (*.json)'
        )
        if not path:
            return
        if self.db.export_ai_corrections_json(path):
            QMessageBox.information(
                self, 'Backup Created',
                f'AI learning data exported to:\n{path}'
            )
        else:
            QMessageBox.critical(self, 'Backup Failed', 'Could not write backup file.')

    def restore_learning_data(self):
        """Restore learning data from a previously exported JSON file."""
        from PyQt6.QtWidgets import QFileDialog
        import os
        data_dir = os.path.dirname(self.db.db_path)
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open Learning Data Backup', data_dir,
            'JSON files (*.json)'
        )
        if not path:
            return

        reply = QMessageBox.question(
            self, 'Confirm Restore',
            f'Import corrections from:\n{os.path.basename(path)}?\n\n'
            'Existing corrections will be kept; imported rows will be merged.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        count = self.db.import_ai_corrections_json(path)
        if count >= 0:
            self.refresh_learning_data()
            self.statusBar().showMessage(f'Imported {count} correction(s) from backup.', 4000)
            QMessageBox.information(
                self, 'Restore Complete',
                f'Imported {count} correction(s) from:\n{os.path.basename(path)}'
            )
        else:
            QMessageBox.critical(self, 'Restore Failed', 'Could not read backup file.')
    
    def setup_table_delegates(self):
        """Setup dropdown delegates for table columns using controlled vocabularies"""
        try:
            # Column mapping: column_index -> field_name
            vocab_columns = {
                self.COL_SCENE: 'scene_type',
                self.COL_MOOD: 'mood',
                self.COL_SUBJECTS: 'subjects',
                self.COL_LOCATION: 'location',
            }

            for col, field in vocab_columns.items():
                vocab = self.db.get_vocabulary(field)
                if vocab:
                    vocab_with_unknown = ['unknown'] + vocab
                    delegate = ComboBoxDelegate(vocab_with_unknown)
                    self.photo_table.setItemDelegateForColumn(col, delegate)
        except Exception as e:
            print(f"Error setting up delegates: {e}")
    
    def browse_folder(self):
        """Open folder selection dialog"""
        current_folder = self.folder_input.text()
        if current_folder and os.path.exists(current_folder):
            start_dir = current_folder
        else:
            start_dir = ""
        
        folder = QFileDialog.getExistingDirectory(self, "Select Root Folder", start_dir)
        if folder:
            self.folder_input.setText(folder)
            self.save_last_folder(folder)
            self._start_folder_watcher(folder)
            # Optionally refresh UI immediately
            self.refresh_photos()

    def _start_folder_watcher(self, folder: str):
        """Start (or restart) the background folder watcher for the given folder."""
        try:
            # Stop any existing watcher
            fw = getattr(self, '_folder_watcher', None)
            if fw and fw.isRunning():
                fw.stop()
                fw.wait(1000)

            from core.folder_watcher import FolderWatcher
            include_sub = self.subfolder_checkbox.isChecked() if hasattr(self, 'subfolder_checkbox') else True
            # Read watcher interval from Settings tab if available (default 30s)
            interval = 30
            try:
                st = getattr(self, 'settings_tab', None)
                if st and hasattr(st, 'watcher_interval_spin'):
                    interval = st.watcher_interval_spin.value()
            except Exception:
                pass
            self._folder_watcher = FolderWatcher(folder, self.db, interval_secs=interval,
                                                  include_subfolders=include_sub)
            self._folder_watcher.new_photo_found.connect(self._on_new_photo_found)
            self._folder_watcher.status_update.connect(
                lambda msg: self.statusBar().showMessage(msg, 3000) if self.statusBar() else None
            )
            self._folder_watcher.start()
        except Exception as e:
            print(f"[FolderWatcher] Could not start: {e}")

    def _on_new_photo_found(self, filepath: str):
        """Handle a new file detected by the folder watcher — add it to DB."""
        try:
            from core.exif_extractor import extract_exif
            from core.duplicate_detector import perceptual_hash, md5_hash

            meta = extract_exif(filepath)
            meta['perceptual_hash'] = perceptual_hash(filepath)
            meta['file_hash'] = md5_hash(filepath)
            photo_id = self.db.add_photo(filepath, meta)
            photo_data = self.db.get_photo(photo_id)
            if photo_data:
                self.add_photo_to_table(photo_data)
                self.refresh_gallery()
                if self.statusBar():
                    self.statusBar().showMessage(
                        f"New photo detected: {Path(filepath).name}", 4000
                    )
        except Exception as e:
            print(f"[FolderWatcher] Error importing {filepath}: {e}")
    
    def save_last_folder(self, folder):
        """Save the last used folder to settings"""
        self.settings.setValue("last_folder", folder)
        self.settings.sync()  # Force write to disk
        print(f"Saved folder to settings: {folder}")

    def relink_filepaths(self):
        """Update stored photo paths to use the currently selected root folder."""
        new_root = self.folder_input.text().strip()
        if not new_root or not os.path.isdir(new_root):
            QMessageBox.warning(self, "Invalid Folder", "Please select a valid root folder before relinking.")
            return

        photos = self.db.get_all_photos()
        if not photos:
            QMessageBox.information(self, "No Photos", "Database has no photos to relink.")
            return

        # Determine old root
        old_root = self.settings.value("last_folder", "")
        # Try deriving a common path across stored filepaths (case-insensitive), tolerate different drives
        if not old_root:
            try:
                norm_paths = [os.path.normcase(os.path.normpath(p["filepath"])) for p in photos if p.get("filepath")]
                if norm_paths:
                    # String-based common prefix, then trim to the last path separator
                    cp = os.path.commonprefix(norm_paths)
                    last_sep_idx = max(cp.rfind("/"), cp.rfind("\\"))
                    if last_sep_idx > 0:
                        old_root = cp[:last_sep_idx]
            except Exception:
                old_root = ""

        # If still unknown, ask user to select previous root
        if not old_root:
            QMessageBox.information(
                self,
                "Select Previous Root",
                "Could not auto-detect the previous root folder.\n\n"
                "Please select the folder that previously contained your photos (the old location)."
            )
            chosen = QFileDialog.getExistingDirectory(self, "Select Previous Root Folder", "")
            if chosen:
                old_root = chosen
            else:
                QMessageBox.warning(self, "Unable to Detect Old Root", "Could not determine the previous root folder for stored paths.")
                return

        if os.path.normcase(os.path.normpath(old_root)) == os.path.normcase(os.path.normpath(new_root)):
            QMessageBox.information(self, "No Change", "The selected folder matches the current root; no relink needed.")
            return

        # Optional: build filename index under new_root for fallback matching
        fname_index = {}
        try:
            for root, _dirs, files in os.walk(new_root):
                for f in files:
                    fname_index.setdefault(f.lower(), os.path.join(root, f))
        except Exception:
            fname_index = {}

        def try_relative(fp_str: str, old_root_str: str):
            # Case-insensitive prefix check for Windows
            a = os.path.normcase(os.path.normpath(fp_str))
            b = os.path.normcase(os.path.normpath(old_root_str))
            if a.startswith(b):
                rel = a[len(b):].lstrip("/\\")
                return rel
            return None

        updated = 0
        by_name = 0
        skipped = 0
        for photo in photos:
            fp = photo.get("filepath")
            if not fp:
                skipped += 1
                continue

            rel = try_relative(fp, old_root)
            new_path = None
            if rel:
                candidate = os.path.join(new_root, rel)
                if os.path.exists(candidate):
                    new_path = candidate
            # Fallback: match by filename anywhere under new_root
            if not new_path:
                fname = os.path.basename(fp).lower()
                match = fname_index.get(fname)
                if match and os.path.exists(match):
                    new_path = match
                    by_name += 1

            if not new_path:
                skipped += 1
                continue

            self.db.update_photo_metadata(photo["id"], {"filepath": str(new_path), "filename": os.path.basename(new_path)})
            updated += 1

        self.save_last_folder(new_root)
        self.refresh_photos()
        self.gallery_tab.refresh()

        QMessageBox.information(
            self,
            "Relink Complete",
            f"Updated {updated} photo paths. {by_name} matched by filename. Skipped {skipped}."
        )
    
    def start_analysis(self):
        """Start analyzing images"""
        folder = self.folder_input.text()
        if not folder or not os.path.exists(folder):
            QMessageBox.warning(self, "Error", "Please select a valid folder")
            return
        
        self.analyze_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._live_gallery_update_count = 0
        
        self.analyzer_thread = AnalyzerThread(
            folder,
            self.subfolder_checkbox.isChecked(),
            self.db.db_path  # Use configured DB path
        )
        self.analyzer_thread.progress.connect(self.update_progress)
        self.analyzer_thread.photo_analyzed.connect(self.handle_photo_analyzed)
        self.analyzer_thread.finished.connect(self.analysis_finished)
        self.analyzer_thread.error.connect(self.analysis_error)
        self.analyzer_thread.start()

    def handle_photo_analyzed(self, photo):
        """Update Library and Gallery incrementally as photos are analyzed."""
        self.add_photo_to_table(photo)
        self._live_gallery_update_count += 1

        # Throttle gallery redraws to keep analysis responsive on large batches.
        if self._live_gallery_update_count == 1 or self._live_gallery_update_count % 5 == 0:
            self.refresh_gallery()
    
    def update_progress(self, current, total, filename):
        """Update progress bar"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Analyzing {current}/{total}: {filename}")
    
    def analysis_finished(self):
        """Called when analysis is complete"""
        self.analyze_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Analysis complete!")
        QMessageBox.information(self, "Complete", "Image analysis finished!")
        self.refresh_photos()
        self.refresh_gallery()
    
    def analysis_error(self, error_msg):
        """Called when an error occurs"""
        QMessageBox.warning(self, "Error", f"An error occurred: {error_msg}")
        self.status_label.setText(f"Error: {error_msg}")
    
    def add_photo_to_table(self, photo):
        """Add a single photo to the table"""
        is_batch_analyzing = bool(
            getattr(self, 'analyzer_thread', None)
            and self.analyzer_thread.isRunning()
        )

        photos_tab = getattr(self, 'photos_tab', None)
        selected_ids = getattr(photos_tab, 'persistent_selected_ids', getattr(self, 'persistent_selected_ids', set()))
        thumb_sizes = getattr(photos_tab, 'thumbnail_sizes', getattr(self, 'thumbnail_sizes', {'off': 0, 'small': 50, 'medium': 100, 'large': 150}))
        current_thumb_size = getattr(photos_tab, 'current_thumb_size', getattr(self, 'current_thumb_size', 'medium'))

        row = self.photo_table.rowCount()
        self.photo_table.insertRow(row)
        
        # Block signals and sorting while populating
        self.photo_table.blockSignals(True)
        self.photo_table.setSortingEnabled(False)
        
        # Set row height based on thumbnail size
        thumb_size = thumb_sizes.get(current_thumb_size, 100)
        if thumb_size > 0:
            self.photo_table.setRowHeight(row, thumb_size + 10)
        
        # Checkbox column (column 0) - use an actual QCheckBox widget for reliability
        chk = QCheckBox()
        chk.setTristate(False)
        chk.setChecked(photo['id'] in selected_ids)
        chk.setProperty('photo_id', int(photo['id']))
        chk.stateChanged.connect(self.on_row_checkbox_toggled)
        # Center the checkbox
        chk_container = QWidget()
        c_layout = QHBoxLayout(chk_container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.addWidget(chk, alignment=Qt.AlignmentFlag.AlignCenter)
        self.photo_table.setCellWidget(row, self.COL_CHECKBOX, chk_container)
        
        # ID column - read only (now column 1)
        id_item = QTableWidgetItem(f"{photo['id']:06d}")
        id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.photo_table.setItem(row, self.COL_ID, id_item)
        
        # Add thumbnail (now column 2). During active batch analysis, defer
        # expensive thumbnail generation until the final refresh.
        if is_batch_analyzing:
            self.photo_table.setItem(row, self.COL_THUMBNAIL, QTableWidgetItem(""))
        else:
            self.add_thumbnail(row, self.COL_THUMBNAIL, photo['filepath'])
        
        self.photo_table.setItem(row, self.COL_SCENE, QTableWidgetItem(photo.get('scene_type') or ''))
        self.photo_table.setItem(row, self.COL_MOOD, QTableWidgetItem(photo.get('mood') or ''))
        self.photo_table.setItem(row, self.COL_SUBJECTS, QTableWidgetItem(photo.get('subjects') or ''))
        location_item = QTableWidgetItem(photo.get('location') or '')
        location_item.setToolTip(f"Location: {photo.get('location') or 'Not set'}")
        self.photo_table.setItem(row, self.COL_LOCATION, location_item)
        self.photo_table.setItem(row, self.COL_OBJECTS, QTableWidgetItem(photo.get('objects_detected') or ''))

        # Status text
        status_map = {'raw': 'Unreviewed', 'needs_edit': 'Editing', 'ready': 'Ready', 'released': 'Published'}
        self.photo_table.setItem(row, self.COL_STATUS, QTableWidgetItem(status_map.get(photo.get('status', 'raw'), 'Unreviewed')))

        # Checkboxes for release status
        ig_item = QTableWidgetItem()
        ig_item.setFlags(ig_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        ig_item.setCheckState(Qt.CheckState.Checked if photo['released_instagram'] else Qt.CheckState.Unchecked)
        self.photo_table.setItem(row, self.COL_IG, ig_item)

        tiktok_item = QTableWidgetItem()
        tiktok_item.setFlags(tiktok_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        tiktok_item.setCheckState(Qt.CheckState.Checked if photo['released_tiktok'] else Qt.CheckState.Unchecked)
        self.photo_table.setItem(row, self.COL_TIKTOK, tiktok_item)
        
        packages = [] if is_batch_analyzing else self.db.get_packages(photo['id'])
        package_display = ', '.join(packages) if packages else (photo.get('package_name') or '')
        self.photo_table.setItem(row, self.COL_PACKAGE, QTableWidgetItem(package_display))
        
        # Tags column (column 17)
        self.photo_table.setItem(row, self.COL_TAGS, QTableWidgetItem(photo['tags'] or ''))
        
        # Date Created - read only (column 18) without fractional seconds
        raw_date = str(photo['date_created'] or '')
        if '.' in raw_date:
            raw_date = raw_date.split('.')[0]
        date_item = QTableWidgetItem(raw_date)
        date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.photo_table.setItem(row, self.COL_DATE, date_item)
        
        # Filepath (column 20)
        filepath_item = QTableWidgetItem(photo['filepath'] or '')
        filepath_item.setToolTip(photo['filepath'] or 'No path')
        self.photo_table.setItem(row, self.COL_FILEPATH, filepath_item)
        
        self.photo_table.blockSignals(False)
        self.photo_table.setSortingEnabled(True)
    
    def get_cached_thumbnail(self, filepath, size):
        """Get or create cached thumbnail"""
        # Generate cache filename based on original file hash and size
        file_hash = hashlib.md5(filepath.encode()).hexdigest()
        cache_file = Path(self.cache_dir) / f"{file_hash}_{size}.jpg"
        
        # Return cached version if it exists and is newer than source
        if cache_file.exists():
            if cache_file.stat().st_mtime >= os.path.getmtime(filepath):
                return QPixmap(str(cache_file))
        
        # Create thumbnail and cache it
        if filepath and os.path.exists(filepath):
            pixmap = QPixmap(filepath)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                # Save to cache
                scaled_pixmap.save(str(cache_file), "JPG", 85)
                return scaled_pixmap
        return None
    
    def show_full_image(self, filepath, photo_id):
        """Show full image in a lightbox dialog with zoom and notes."""
        if not filepath or not os.path.exists(filepath):
            QMessageBox.warning(self, "Image Not Found", "The image file could not be found.")
            return
        try:
            dlg = ImageLightboxDialog(filepath, photo_id, self.db, self)
            dlg.show()
            if not hasattr(self, '_image_dialogs'):
                self._image_dialogs = []
            self._image_dialogs.append(dlg)
        except Exception as e:
            _append_error_log(f"open_lightbox file={filepath} photo_id={photo_id}", type(e), e, e.__traceback__)
            QMessageBox.warning(self, "Lightbox Error", f"Could not open editor popup.\n\n{e}")

    def log_editor_error(self, action, exc):
        try:
            _append_error_log(action, type(exc), exc, exc.__traceback__)
        except Exception:
            pass

    def refresh_photo_row(self, photo_id: int):
        """Refresh a single photo row in the Library table by photo_id."""
        try:
            photo = self.db.get_photo(photo_id)
            if not photo:
                return
            # Find the row index by searching for this photo_id
            for row in range(self.photo_table.rowCount()):
                pid = self.get_photo_id_from_row(row)
                if pid == photo_id:
                    # Update Notes cell for this row
                    self.photo_table.setItem(row, self.COL_NOTES, QTableWidgetItem(photo.get('notes') or ''))
                    break
        except Exception as e:
            print(f"refresh_photo_row error: {e}")
    
    def add_thumbnail(self, row, col, filepath):
        """Add thumbnail image to table cell"""
        thumb_size = self.thumbnail_sizes[self.current_thumb_size]
        
        if thumb_size == 0:
            # No thumbnail
            self.photo_table.setItem(row, col, QTableWidgetItem(""))
            return
        
        try:
            if filepath and os.path.exists(filepath):
                # Get cached thumbnail
                pixmap = self.get_cached_thumbnail(filepath, thumb_size)
                
                if pixmap and not pixmap.isNull():
                    label = QLabel()
                    label.setPixmap(pixmap)
                    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    label.setCursor(Qt.CursorShape.PointingHandCursor)
                    label.setToolTip("Click to view full image (middle-click opens folder)")
                    
                    # Click handler: left = open image, middle = open folder only
                    pid = self.get_photo_id_from_row(row)
                    label.mousePressEvent = lambda event, fp=filepath, lbl=label, photo_id=pid: self.handle_thumbnail_mouse_press(lbl, event, fp, photo_id)
                    
                    self.photo_table.setCellWidget(row, col, label)
                else:
                    self.photo_table.setItem(row, col, QTableWidgetItem("[No Preview]"))
            else:
                self.photo_table.setItem(row, col, QTableWidgetItem("[Missing]"))
        except Exception as e:
            self.photo_table.setItem(row, col, QTableWidgetItem(f"[Error: {e}]"))

    def handle_thumbnail_mouse_press(self, label, event, filepath, photo_id):
        """Handle thumbnail click: left opens image, middle opens containing folder."""
        try:
            if event.button() == Qt.MouseButton.MiddleButton:
                folder = os.path.dirname(filepath)
                if folder and os.path.isdir(folder):
                    os.startfile(folder)
                event.accept()
                return
            if event.button() == Qt.MouseButton.LeftButton:
                self.show_full_image(filepath, photo_id)
                event.accept()
                return
        except Exception as e:
            print(f"thumbnail click error: {e}")
        event.ignore()
    
    def toggle_thumbnail_size(self):
        """Delegate to PhotosTab."""
        if hasattr(self, 'photos_tab') and self.photos_tab:
            self.photos_tab.toggle_thumbnail_size()
    
    def refresh_photos(self):
        """Delegate to PhotosTab."""
        if hasattr(self, 'photos_tab') and self.photos_tab:
            self.photos_tab.refresh()
    
    def refresh_gallery(self):
        """Delegate to GalleryTab.refresh."""
        if hasattr(self, 'gallery_tab') and self.gallery_tab:
            self.gallery_tab.refresh()
    
    def refresh_gallery_with_photos(self, photos):
        if hasattr(self, 'gallery_tab') and self.gallery_tab:
            self.gallery_tab.refresh_with_photos(list(photos))
    
    def create_gallery_thumbnail(self, photo, size):
        return self.gallery_tab._create_thumbnail(photo, size) if hasattr(self, 'gallery_tab') else None
    
    def handle_gallery_thumbnail_click(self, event, filepath, photo_id):
        if hasattr(self, 'gallery_tab') and self.gallery_tab:
            self.gallery_tab._handle_thumbnail_click(event, filepath, photo_id)
    
    def show_photo_details(self, photo):
        if hasattr(self, 'gallery_tab') and self.gallery_tab:
            self.gallery_tab.show_details(photo)
    
    def save_gallery_details(self):
        if hasattr(self, 'gallery_tab') and self.gallery_tab:
            self.gallery_tab.save_details()
    
    def mark_selected(self, field, value):
        """Mark checked/selected photos with a value"""
        photo_ids = self.get_target_photo_ids()
        if photo_ids:
            self.db.bulk_update(set(photo_ids), {field: value})
            self.refresh_photos()
            self.status_label.setText(f"Updated {len(photo_ids)} photo(s)")
    
    def apply_package(self):
        """Delegate to PhotosTab."""
        if hasattr(self, 'photos_tab') and self.photos_tab:
            self.photos_tab.apply_package()

    def set_package_popup(self):
        """Prompt for package name and apply to selected photos"""
        text, ok = QInputDialog.getText(self, "Set Package", "Package name:", QLineEdit.EchoMode.Normal, self.batch_package.text())
        if not ok:
            return
        # Allow comma-separated multiple packages
        packages = [p.strip() for p in text.split(',') if p.strip()]
        if not packages:
            QMessageBox.warning(self, "Error", "Please enter a package name")
            return

        target_ids = self.get_target_photo_ids()
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check photos to update (or select cells)")
            return
        id_to_row = self.map_photo_ids_to_rows(set(target_ids))
        for pid in target_ids:
            self.db.set_packages(pid, packages)
            row = id_to_row.get(pid)
            if row is not None:
                self.photo_table.item(row, self.COL_PACKAGE).setText(', '.join(packages))

        self.batch_package.setText(', '.join(packages))
        self.statusBar().showMessage(f"Updated {len(target_ids)} photos with packages: {', '.join(packages)}", 3000)

    def manage_packages_dialog(self):
        """Open chip-style Manage Packages dialog and apply to selected photos"""
        target_ids = self.get_target_photo_ids()
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check photos to update (or select cells)")
            return
        # Seed with the first checked/selected photo's packages
        first_id = next(iter(target_ids))
        if first_id is None:
            QMessageBox.information(self, "No Selection", "Could not read selected photo IDs")
            return
        initial = self.db.get_packages(first_id)
        if not initial:
            legacy = self.db.get_photo(first_id).get('package_name') or ''
            if legacy:
                initial = [legacy]

        dlg = PackageManagerDialog(self, initial_packages=initial)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            pkgs = dlg.get_packages()
            if not pkgs:
                # If cleared, clear packages for all
                id_to_row = self.map_photo_ids_to_rows(set(target_ids))
                for pid in target_ids:
                    self.db.set_packages(pid, [])
                    row = id_to_row.get(pid)
                    if row is not None:
                        self.photo_table.item(row, self.COL_PACKAGE).setText('')
                self.statusBar().showMessage(f"Cleared packages for {len(target_ids)} photo(s)", 3000)
                return
            # Apply to all selected
            id_to_row = self.map_photo_ids_to_rows(set(target_ids))
            for pid in target_ids:
                self.db.set_packages(pid, pkgs)
                row = id_to_row.get(pid)
                if row is not None:
                    self.photo_table.item(row, self.COL_PACKAGE).setText(', '.join(pkgs))
            self.batch_package.setText(', '.join(pkgs))
            self.statusBar().showMessage(f"Updated {len(target_ids)} photo(s) with packages", 3000)
    
    def apply_filters(self):
        """Apply filters to photo list. All filter state is read from FiltersTab."""
        all_photos = self.db.get_all_photos()

        # All filter widgets live on the FiltersTab instance.
        _ft = getattr(self, 'filters_tab', None)

        # ── Status ───────────────────────────────────────────────────
        status_filters = []
        if _ft and _ft.filter_raw.isChecked():
            status_filters.append('raw')
        if _ft and _ft.filter_needs_edit.isChecked():
            status_filters.append('needs_edit')
        if _ft and _ft.filter_ready.isChecked():
            status_filters.append('ready')
        if _ft and _ft.filter_released.isChecked():
            status_filters.append('released')

        show_only_unknowns = _ft.filter_unknowns.isChecked() if _ft else False

        # ── Metadata ─────────────────────────────────────────────────
        def _combo(_ft, attr):
            w = getattr(_ft, attr, None)
            v = w.currentText() if w else ''
            return '' if v in ('', '(Any)') else v

        def _text(_ft, attr):
            w = getattr(_ft, attr, None)
            return w.text().strip().lower() if w else ''

        filter_scene = _combo(_ft, 'filter_scene')
        filter_mood = _combo(_ft, 'filter_mood')
        filter_subjects = _combo(_ft, 'filter_subjects')
        filter_location = _text(_ft, 'filter_location')
        filter_package = _text(_ft, 'filter_package')
        filter_quality = _combo(_ft, 'filter_quality')
        filter_tag = _text(_ft, 'filter_tag')
        filter_content_rating = _combo(_ft, 'filter_content_rating')
        filter_has_exif = _ft.filter_has_exif.isChecked() if _ft else False
        filter_has_gps = _ft.filter_has_gps.isChecked() if _ft else False
        filter_ig = _ft.filter_ig.isChecked() if _ft else False
        filter_tiktok = _ft.filter_tiktok.isChecked() if _ft else False

        # Filter photos
        filtered_photos = []
        for photo in all_photos:
            # Unknown values filter
            if show_only_unknowns:
                ai_fields = ['scene_type', 'mood', 'subjects', 'location']
                if not any(not photo.get(f) for f in ai_fields):
                    continue

            # Status filter
            if status_filters and photo.get('status', 'raw') not in status_filters:
                continue

            # Platform filters
            if filter_ig and not photo['released_instagram']:
                continue
            if filter_tiktok and not photo['released_tiktok']:
                continue

            # Metadata filters (case-insensitive partial match)
            if filter_scene and filter_scene.lower() not in (photo.get('scene_type') or '').lower():
                continue
            if filter_mood and filter_mood.lower() not in (photo.get('mood') or '').lower():
                continue
            if filter_subjects and filter_subjects.lower() not in (photo.get('subjects') or '').lower():
                continue
            if filter_location and filter_location not in (photo.get('location') or '').lower():
                continue
            if filter_package:
                pkgs = self.db.get_packages(photo['id'])
                pkg_match = any(filter_package in p.lower() for p in pkgs)
                legacy_match = filter_package in (photo.get('package_name') or '').lower()
                if not (pkg_match or legacy_match):
                    continue
            if filter_quality and (photo.get('quality') or '') != filter_quality:
                continue
            if filter_has_exif and not photo.get('exif_camera'):
                continue
            if filter_has_gps and not (photo.get('exif_gps_lat') and photo.get('exif_gps_lon')):
                continue
            if filter_tag and filter_tag not in (photo.get('tags') or '').lower():
                continue
            if filter_content_rating and (photo.get('content_rating') or 'general') != filter_content_rating:
                continue

            filtered_photos.append(photo)
        
        # Populate table with filtered results
        self.photo_table.setSortingEnabled(False)
        self.photo_table.setRowCount(0)
        self.photo_table.setRowCount(len(filtered_photos))
        
        for i, photo in enumerate(filtered_photos):
            # Set row height based on thumbnail size
            thumb_size = self.thumbnail_sizes[self.current_thumb_size]
            if thumb_size > 0:
                self.photo_table.setRowHeight(i, thumb_size + 10)
            
            # ID column - read only
            id_item = QTableWidgetItem(f"{photo['id']:06d}")
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.photo_table.setItem(i, 0, id_item)
            
            # Add thumbnail
            self.add_thumbnail(i, 1, photo['filepath'])

            # AI metadata columns (new general fields)
            self.photo_table.setItem(i, self.COL_SCENE, QTableWidgetItem(photo.get('scene_type') or ''))
            self.photo_table.setItem(i, self.COL_MOOD, QTableWidgetItem(photo.get('mood') or ''))
            self.photo_table.setItem(i, self.COL_SUBJECTS, QTableWidgetItem(photo.get('subjects') or ''))
            self.photo_table.setItem(i, self.COL_LOCATION, QTableWidgetItem(photo.get('location') or ''))
            self.photo_table.setItem(i, self.COL_OBJECTS, QTableWidgetItem(photo.get('objects_detected') or ''))

            # Status text
            status_map = {'raw': 'Unreviewed', 'needs_edit': 'Editing', 'ready': 'Ready', 'released': 'Published'}
            self.photo_table.setItem(i, self.COL_STATUS, QTableWidgetItem(status_map.get(photo.get('status', 'raw'), 'Unreviewed')))

            # Checkboxes for release status
            ig_item = QTableWidgetItem()
            ig_item.setFlags(ig_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            ig_item.setCheckState(Qt.CheckState.Checked if photo['released_instagram'] else Qt.CheckState.Unchecked)
            self.photo_table.setItem(i, self.COL_IG, ig_item)

            tiktok_item = QTableWidgetItem()
            tiktok_item.setFlags(tiktok_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            tiktok_item.setCheckState(Qt.CheckState.Checked if photo['released_tiktok'] else Qt.CheckState.Unchecked)
            self.photo_table.setItem(i, self.COL_TIKTOK, tiktok_item)

            packages = self.db.get_packages(photo['id'])
            package_display = ', '.join(packages) if packages else (photo.get('package_name') or '')
            self.photo_table.setItem(i, self.COL_PACKAGE, QTableWidgetItem(package_display))

            self.photo_table.setItem(i, self.COL_TAGS, QTableWidgetItem(photo.get('tags') or ''))

            # Date Created - read only, without fractional seconds
            raw_date = str(photo['date_created'] or '')
            if '.' in raw_date:
                raw_date = raw_date.split('.')[0]
            date_item = QTableWidgetItem(raw_date)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.photo_table.setItem(i, self.COL_DATE, date_item)

            filepath_item = QTableWidgetItem(photo['filepath'] or '')
            filepath_item.setToolTip(photo['filepath'] or 'No path')
            self.photo_table.setItem(i, self.COL_FILEPATH, filepath_item)

            self.photo_table.setItem(i, self.COL_NOTES, QTableWidgetItem(photo.get('notes') or ''))
        
        self.photo_table.setSortingEnabled(True)
        self.statusBar().showMessage(f"Filtered: {len(filtered_photos)} of {len(all_photos)} photos", 5000)
        
        # Also refresh gallery with filtered results
        self.refresh_gallery_with_photos(filtered_photos)
    
    def clear_filters(self):
        """Clear all filters and show all photos."""
        _ft = getattr(self, 'filters_tab', None)
        if _ft:
            _ft.clear_filters()
        self.refresh_photos()
        self.refresh_gallery()
        self.statusBar().showMessage("Filters cleared", 3000)
    
    def on_table_item_changed(self, item):
        """Delegate to PhotosTab."""
        if hasattr(self, 'photos_tab') and self.photos_tab:
            self.photos_tab.on_table_item_changed(item)
    
    def bulk_edit_cells(self):
        """Bulk edit selected cells with the same value"""
        selected_items = self.photo_table.selectedItems()
        
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select cells to edit")
            return
        
        # Filter out non-editable columns (checkbox, ID, thumbnail, release toggles, date)
        non_editable = [self.COL_CHECKBOX, self.COL_ID, self.COL_THUMBNAIL, self.COL_IG, self.COL_TIKTOK, self.COL_DATE]
        editable_items = [item for item in selected_items if item.column() not in non_editable]
        
        if not editable_items:
            QMessageBox.information(self, "No Editable Cells", "Please select editable metadata cells (not ID, Thumbnail, Date, or checkboxes)")
            return
        
        # Get the column name for display
        column_names = {
            self.COL_SCENE: 'Scene',
            self.COL_MOOD: 'Mood',
            self.COL_SUBJECTS: 'Subjects',
            self.COL_LOCATION: 'Location',
            self.COL_OBJECTS: 'Objects',
            self.COL_STATUS: 'Status',
            self.COL_PACKAGE: 'Package',
            self.COL_TAGS: 'Tags',
            self.COL_FILEPATH: 'Filepath'
        }
        
        # Check if all selected cells are in the same column
        columns = set(item.column() for item in editable_items)
        if len(columns) == 1:
            col = list(columns)[0]
            col_name = column_names.get(col, f"Column {col}")
        else:
            col_name = "multiple columns"
        
        # Prompt for new value
        text, ok = QInputDialog.getText(self, "Bulk Edit", 
                                        f"Enter new value for {len(editable_items)} cell(s) in {col_name}:")
        
        if ok:
            # Column mapping to database fields
            column_to_field = self.COLUMN_TO_FIELD
            
            # Block signals to prevent individual updates
            self.photo_table.blockSignals(True)
            
            # AI fields that should track corrections
            ai_fields = ['scene_type', 'mood', 'subjects', 'location', 'objects_detected']
            
            updates = []
            tags_updated = False
            for item in editable_items:
                col = item.column()
                row = item.row()
                photo_id = self.get_photo_id_from_row(row)
                if photo_id is None:
                    continue

                if col == self.COL_STATUS:  # Status - special handling
                    status_map = {'Unreviewed': 'raw', 'Editing': 'needs_edit', 'Ready': 'ready', 'Published': 'released'}
                    # Also accept old display names for backwards compat
                    status_map.update({'Raw': 'raw', 'Needs Edit': 'needs_edit', 'Ready for Release': 'ready', 'Released': 'released'})
                    db_value = status_map.get(text, text.lower().replace(' ', '_'))
                    self.db.update_photo_metadata(photo_id, {'status': db_value})
                    display_map = {'raw': 'Unreviewed', 'needs_edit': 'Editing', 'ready': 'Ready', 'released': 'Published'}
                    item.setText(display_map.get(db_value, text))
                elif col in column_to_field:
                    field_name = column_to_field[col]
                    if field_name == 'package_name':
                        packages = [p.strip() for p in text.split(',') if p.strip()]
                        self.db.set_packages(photo_id, packages)
                        item.setText(', '.join(packages))
                        continue
                    
                    # Track corrections for AI fields
                    if field_name in ai_fields:
                        photo = self.db.get_photo(photo_id)
                        original_value = photo.get(field_name)
                        if original_value and original_value != text:
                            self.db.save_correction(photo_id, field_name, original_value, text)
                    
                    self.db.update_photo_metadata(photo_id, {field_name: text})
                    item.setText(text)
                    if field_name == 'tags':
                        tags_updated = True
                
                updates.append(photo_id)
            
            # Re-enable signals
            self.photo_table.blockSignals(False)
            
            # Refresh tag cloud if tags were updated
            if tags_updated:
                self.refresh_tag_cloud()
            
            self.statusBar().showMessage(f"Updated {len(editable_items)} cell(s) across {len(set(updates))} photo(s)", 3000)
    
    def apply_status_to_selected(self):
        """Apply chosen status to checked/selected photos"""
        target_ids = set(self.get_target_photo_ids())
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check photos to update (or select cells)")
            return
        id_to_row = self.map_photo_ids_to_rows(target_ids)
        
        status_text = self.status_dropdown.currentText()
        status_map = {'Unreviewed': 'raw', 'Editing': 'needs_edit', 'Ready': 'ready', 'Published': 'released'}
        status_value = status_map.get(status_text, 'raw')
        
        # Update database and table
        updated = 0
        for pid in target_ids:
            self.db.update_photo_metadata(pid, {'status': status_value})
            row = id_to_row.get(pid)
            if row is not None:
                self.photo_table.item(row, self.COL_STATUS).setText(status_text)
            updated += 1
        
        self.statusBar().showMessage(f"Updated {updated} photos to {status_text}", 3000)
    
    def toggle_release_status(self, platform):
        """Toggle release status for checked/selected photos"""
        target_ids = set(self.get_target_photo_ids())
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check photos (or select cells)")
            return
        id_to_row = self.map_photo_ids_to_rows(target_ids)
        
        column_map = {
            'released_instagram': self.COL_IG,
            'released_tiktok': self.COL_TIKTOK,
        }
        col = column_map[platform]
        
        # Toggle checkboxes
        for pid in target_ids:
            row = id_to_row.get(pid)
            # Update DB release flag
            item = self.photo_table.item(row, col) if row is not None else None
            new_state = not (item.checkState() == Qt.CheckState.Checked) if item is not None else True
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked if new_state else Qt.CheckState.Unchecked)
            self.db.update_photo_metadata(pid, {platform: 1 if new_state else 0})
            # If marking as released, move to released folder structure
            if new_state:
                dest_path = self.move_to_released(pid, platform)
                if dest_path:
                    if row is not None:
                        self.photo_table.item(row, self.COL_FILEPATH).setText(dest_path)
        
        platform_name = platform.replace('released_', '').title()
        self.statusBar().showMessage(f"Toggled {platform_name} for {len(target_ids)} photos", 3000)
    
    def reanalyze_selected(self):
        """Re-analyze selected photos using AI with learned corrections"""
        target_ids = list(self.get_target_photo_ids())
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check photos to re-analyze (or select cells)")
            return
        photos_to_analyze = []
        for photo_id in target_ids:
            photo = self.db.get_photo(photo_id)
            if photo and photo.get('filepath'):
                photos_to_analyze.append(photo)
        if not photos_to_analyze:
            return
        
        # Simple synchronous version
        progress = QProgressDialog(f"Re-analyzing {len(photos_to_analyze)} photos...", "Cancel", 0, len(photos_to_analyze), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        
        for i, photo in enumerate(photos_to_analyze):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            progress.setLabelText(f"Re-analyzing {photo.get('filename', 'Unknown')}...")
            QApplication.processEvents()
            
            try:
                # Re-analyze with AI
                metadata = analyze_image(photo['filepath'], self.db)
                
                # Get fields that user has manually corrected
                corrected_fields = self.db.get_corrected_fields_for_photo(photo['id'])
                
                # Preserve user corrections
                if corrected_fields:
                    for field in corrected_fields:
                        if field in metadata:
                            del metadata[field]
                
                # Update database
                if metadata:
                    self.db.update_photo_metadata(photo['id'], metadata)
            except Exception as e:
                print(f"Error re-analyzing {photo.get('filename')}: {e}")
        
        progress.setValue(len(photos_to_analyze))
        self.refresh_photos()
        self.refresh_gallery()
        self.statusBar().showMessage(f"Re-analyzed {len(photos_to_analyze)} photos", 3000)
    
    def update_reanalyze_progress(self, current, total, status):
        """Update progress bar for re-analysis"""
        self.progress_bar.setValue(current)
        self.progress_bar.setMaximum(total)
        self.status_label.setText(f"Re-analyzing {current}/{total}: {status}")
    
    def reanalysis_finished(self):
        """Handle re-analysis completion"""
        self.analyze_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Re-analysis complete")
        
        # Refresh table to show updated data
        self.refresh_photos()
        self.refresh_gallery()
        
        self.statusBar().showMessage("Re-analysis complete!", 3000)
    
    def select_all_photos(self):
        """Select all photos in the table"""
        row_count = self.photo_table.rowCount()
        # Check all row checkboxes and update persistent set
        for row in range(row_count):
            chk_container = self.photo_table.cellWidget(row, self.COL_CHECKBOX)
            if chk_container and chk_container.layout() and chk_container.layout().count():
                chk = chk_container.layout().itemAt(0).widget()
                if isinstance(chk, QCheckBox):
                    chk.blockSignals(True)
                    chk.setChecked(True)
                    chk.blockSignals(False)
            pid = self.get_photo_id_from_row(row)
            if pid is not None:
                self.persistent_selected_ids.add(pid)
        
        self.statusBar().showMessage(f"Selected all {row_count} photos", 2000)
    
    def deselect_all_photos(self):
        """Deselect all photos in the table"""
        row_count = self.photo_table.rowCount()
        for row in range(row_count):
            chk_container = self.photo_table.cellWidget(row, self.COL_CHECKBOX)
            if chk_container and chk_container.layout() and chk_container.layout().count():
                chk = chk_container.layout().itemAt(0).widget()
                if isinstance(chk, QCheckBox):
                    chk.blockSignals(True)
                    chk.setChecked(False)
                    chk.blockSignals(False)
        self.persistent_selected_ids.clear()
        self.statusBar().showMessage("Cleared selection", 2000)
    
    def cancel_analysis(self):
        """Cancel the ongoing analysis or re-analysis"""
        if self.analyzer_thread and self.analyzer_thread.isRunning():
            self.analyzer_thread.stop()
            self.statusBar().showMessage('Cancelling analysis...', 3000)
            self.cancel_btn.setEnabled(False)
            self.analyze_btn.setEnabled(True)
    
    def refresh_tag_cloud(self):
        """Refresh the tag cloud display"""
        # Check if tag cloud has been created yet
        if not hasattr(self, 'tag_cloud_layout'):
            return
        
        # Clear existing tags
        while self.tag_cloud_layout.count():
            item = self.tag_cloud_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.tag_buttons.clear()
        
        # Get all tags with counts
        tags = self.db.get_all_tags()
        
        if not tags:
            no_tags_label = QLabel("No tags yet. Add tags to photos to see them here!")
            no_tags_label.setStyleSheet("color: gray; font-style: italic;")
            self.tag_cloud_layout.addWidget(no_tags_label)
            return
        
        # Create button for each tag
        for tag, count in tags:
            btn = QPushButton(f"{tag} ({count})")
            btn.setProperty('tag', tag)  # Store tag name in button
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.setChecked(tag in self.active_tags)
            
            # Set initial style based on active state
            self.update_tag_button_style(btn, tag in self.active_tags)
            
            btn.clicked.connect(lambda checked, t=tag, b=btn: self.toggle_tag_filter(t, b))
            self.tag_cloud_layout.addWidget(btn)
            self.tag_buttons[tag] = btn
        
        self.tag_cloud_layout.addStretch()
    
    def update_tag_button_style(self, btn, is_active):
        """Update tag button style based on active state"""
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    border: 2px solid #0078d4;
                    border-radius: 12px;
                    padding: 5px 15px;
                    margin: 2px;
                    background-color: #0078d4;
                    color: white;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #106ebe;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #ccc;
                    border-radius: 12px;
                    padding: 5px 15px;
                    margin: 2px;
                    background-color: #e8f4f8;
                }
                QPushButton:hover {
                    background-color: #d0e8f0;
                }
                QPushButton:pressed {
                    background-color: #b8dce8;
                }
            """)
    
    def toggle_tag_filter(self, tag, btn):
        """Toggle a tag filter on/off"""
        if tag in self.active_tags:
            # Remove tag from active set
            self.active_tags.remove(tag)
            self.update_tag_button_style(btn, False)
        else:
            # Add tag to active set
            self.active_tags.add(tag)
            self.update_tag_button_style(btn, True)
        
        # Apply the filter
        self.apply_tag_filters()
    
    def apply_tag_filters(self):
        """Apply current active tag filters"""
        if not self.active_tags:
            # No tags active, show all photos
            self.clear_tag_filter_btn.setVisible(False)
            self.refresh_photos()
            self.refresh_gallery()
            self.status_label.setText("No tag filters active")
            return
        
        self.clear_tag_filter_btn.setVisible(True)
        
        # Get all photos
        all_photos = self.db.get_all_photos()
        
        # Filter photos that have ANY of the active tags
        filtered_photos = []
        for photo in all_photos:
            if photo.get('tags'):
                photo_tags = [t.strip().lower() for t in photo['tags'].split(',') if t.strip()]
                # Check if photo has any of the active tags
                if any(tag in photo_tags for tag in self.active_tags):
                    filtered_photos.append(photo)
        
        # Update table
        self.photo_table.setRowCount(0)
        for photo in filtered_photos:
            self.add_photo_to_table(photo)
        
        # Update gallery
        self.refresh_gallery_with_photos(filtered_photos)
        
        # Update status
        tag_list = ', '.join(sorted(self.active_tags))
        self.status_label.setText(f"Filtered by tags: {tag_list} ({len(filtered_photos)} photos)")
        
        # Switch to Library tab to show results
        self.tabs.setCurrentIndex(1)
    
    def clear_tag_filter(self):
        """Clear all tag filters"""
        self.active_tags.clear()
        self.clear_tag_filter_btn.setVisible(False)
        
        # Update all button styles
        for tag, btn in self.tag_buttons.items():
            btn.setChecked(False)
            self.update_tag_button_style(btn, False)
        
        self.refresh_photos()
        self.refresh_gallery()
        self.status_label.setText("Tag filters cleared")
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.analyzer_thread and self.analyzer_thread.isRunning():
            self.analyzer_thread.stop()
            if not self.analyzer_thread.wait(2000):
                self.analyzer_thread.terminate()
        # Stop scheduler worker
        try:
            w = getattr(self, '_scheduler_worker', None)
            if w and w.isRunning():
                w.stop()
                w.wait(2000)
        except Exception:
            pass
        # Stop folder watcher if running
        try:
            fw = getattr(self, '_folder_watcher', None)
            if fw and fw.isRunning():
                fw.stop()
                fw.wait(1000)
        except Exception:
            pass
        self.db.close()
        event.accept()


def _append_error_log(action, exc_type, exc_value, exc_traceback):
    try:
        log_path = Path("data") / "editor_errors.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] action={action}\n{details}\n")
    except Exception:
        pass


def _prune_editor_error_log():
    """Keep only structured exception blocks and drop raw stderr noise lines."""
    log_path = Path("data") / "editor_errors.log"
    if not log_path.exists():
        return
    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
        kept = []
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            if line.startswith("[") and "action=" in line:
                kept.append(line)
                i += 1
                while i < n and not (lines[i].startswith("[") and "action=" in lines[i]):
                    kept.append(lines[i])
                    i += 1
            else:
                i += 1
        rebuilt = "".join(kept)
        current = "".join(lines)
        if rebuilt != current:
            log_path.write_text(rebuilt, encoding="utf-8")
    except Exception:
        pass


def _global_excepthook(exc_type, exc_value, exc_traceback):
    _append_error_log("unhandled_exception", exc_type, exc_value, exc_traceback)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def _threading_excepthook(args):
    _append_error_log("thread_exception", args.exc_type, args.exc_value, args.exc_traceback)


def _install_exception_hooks():
    _prune_editor_error_log()
    sys.excepthook = _global_excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _threading_excepthook


def main():
    try:
        _install_exception_hooks()
        app = QApplication(sys.argv)
        print("QApplication created successfully")
        window = MainWindow()
        print("MainWindow created successfully")
        window.show()
        print("Window shown successfully")
        print("Starting event loop...")
        result = app.exec()
        print(f"Event loop exited with code: {result}")
        sys.exit(result)
    except Exception as e:
        _append_error_log("main_startup", type(e), e, e.__traceback__)
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == '__main__':
    main()

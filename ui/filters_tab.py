"""
Filters tab — general-purpose photo filtering for PhotoFlow.
"""
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QScrollArea,
)
from PyQt6.QtCore import QSize
from core.icons import icon as _icon


class FiltersTab(QWidget):
    """Encapsulates filtering and search UI."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # --- Status filters ---
        scroll_layout.addWidget(QLabel("<b>Status:</b>"))
        self.filter_raw = QCheckBox("Unreviewed")
        scroll_layout.addWidget(self.filter_raw)
        self.filter_needs_edit = QCheckBox("Editing")
        scroll_layout.addWidget(self.filter_needs_edit)
        self.filter_ready = QCheckBox("Ready")
        scroll_layout.addWidget(self.filter_ready)
        self.filter_released = QCheckBox("Published")
        scroll_layout.addWidget(self.filter_released)

        # --- Quick filters ---
        scroll_layout.addWidget(QLabel("<b>Quick Filters:</b>"))
        self.filter_unknowns = QCheckBox("Show only unanalyzed photos")
        self.filter_unknowns.setToolTip("Show photos with empty AI fields")
        scroll_layout.addWidget(self.filter_unknowns)

        # --- Platform filters ---
        scroll_layout.addWidget(QLabel("<b>Published To:</b>"))
        self.filter_ig = QCheckBox("Instagram")
        scroll_layout.addWidget(self.filter_ig)
        self.filter_tiktok = QCheckBox("TikTok")
        scroll_layout.addWidget(self.filter_tiktok)

        # --- Scene type ---
        scroll_layout.addWidget(QLabel("<b>Scene Type:</b>"))
        self.filter_scene = QComboBox()
        self.filter_scene.addItems([
            "(Any)", "portrait", "landscape", "street", "event", "food",
            "product", "travel", "architecture", "macro", "abstract",
            "sports", "nature", "night", "interior",
        ])
        self.filter_scene.setEditable(True)
        scroll_layout.addWidget(self.filter_scene)

        # --- Mood ---
        scroll_layout.addWidget(QLabel("<b>Mood:</b>"))
        self.filter_mood = QComboBox()
        self.filter_mood.addItems([
            "(Any)", "bright", "dark", "dramatic", "cozy", "energetic",
            "calm", "romantic", "mysterious", "playful",
        ])
        self.filter_mood.setEditable(True)
        scroll_layout.addWidget(self.filter_mood)

        # --- Subjects ---
        scroll_layout.addWidget(QLabel("<b>Subjects:</b>"))
        self.filter_subjects = QComboBox()
        self.filter_subjects.addItems([
            "(Any)", "people", "animal", "vehicle", "building",
            "food", "plant", "sky", "water", "none",
        ])
        self.filter_subjects.setEditable(True)
        scroll_layout.addWidget(self.filter_subjects)

        # --- Quality ---
        scroll_layout.addWidget(QLabel("<b>Quality:</b>"))
        self.filter_quality = QComboBox()
        self.filter_quality.addItems(["(Any)", "excellent", "good", "fair", "poor"])
        scroll_layout.addWidget(self.filter_quality)

        # --- Has EXIF ---
        self.filter_has_exif = QCheckBox("Has EXIF data (camera info)")
        scroll_layout.addWidget(self.filter_has_exif)
        self.filter_has_gps = QCheckBox("Has GPS coordinates")
        scroll_layout.addWidget(self.filter_has_gps)

        # --- Content rating ---
        scroll_layout.addWidget(QLabel("<b>Content Rating:</b>"))
        self.filter_content_rating = QComboBox()
        self.filter_content_rating.addItems(["(Any)", "general", "mature", "restricted"])
        scroll_layout.addWidget(self.filter_content_rating)

        # --- Location ---
        scroll_layout.addWidget(QLabel("<b>Location:</b>"))
        self.filter_location = QLineEdit()
        self.filter_location.setPlaceholderText("e.g. beach, city, studio")
        scroll_layout.addWidget(self.filter_location)

        # --- Tags ---
        scroll_layout.addWidget(QLabel("<b>Tag:</b>"))
        self.filter_tag = QLineEdit()
        self.filter_tag.setPlaceholderText("e.g. sunset, portrait")
        scroll_layout.addWidget(self.filter_tag)

        # --- Package / Album ---
        scroll_layout.addWidget(QLabel("<b>Package / Album:</b>"))
        self.filter_package = QLineEdit()
        self.filter_package.setPlaceholderText("Any package or album name")
        scroll_layout.addWidget(self.filter_package)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        apply_btn = QPushButton("Apply Filters")
        apply_btn.setIcon(_icon('check'))
        apply_btn.setIconSize(QSize(16, 16))
        apply_btn.clicked.connect(self.apply_filters)
        btn_row.addWidget(apply_btn)

        clear_btn = QPushButton("Clear Filters")
        clear_btn.setIcon(_icon('close'))
        clear_btn.setIconSize(QSize(16, 16))
        clear_btn.clicked.connect(self.clear_filters)
        btn_row.addWidget(clear_btn)

        layout.addLayout(btn_row)

    def apply_filters(self):
        """Delegate filter application to the main controller."""
        if hasattr(self.controller, 'apply_filters'):
            self.controller.apply_filters()
        elif self.controller.statusBar():
            self.controller.statusBar().showMessage("Filters applied", 3000)

    def clear_filters(self):
        """Reset all filter widgets to default state and refresh the photo table."""
        self.filter_raw.setChecked(False)
        self.filter_needs_edit.setChecked(False)
        self.filter_ready.setChecked(False)
        self.filter_released.setChecked(False)
        self.filter_unknowns.setChecked(False)
        self.filter_ig.setChecked(False)
        self.filter_tiktok.setChecked(False)
        self.filter_scene.setCurrentIndex(0)
        self.filter_mood.setCurrentIndex(0)
        self.filter_subjects.setCurrentIndex(0)
        self.filter_quality.setCurrentIndex(0)
        self.filter_has_exif.setChecked(False)
        self.filter_has_gps.setChecked(False)
        self.filter_content_rating.setCurrentIndex(0)
        self.filter_location.clear()
        self.filter_tag.clear()
        self.filter_package.clear()
        # Refresh the photo table via the controller's clear_filters path
        if hasattr(self.controller, 'refresh_photos'):
            self.controller.refresh_photos()
        if hasattr(self.controller, 'refresh_gallery'):
            self.controller.refresh_gallery()
        if self.controller.statusBar():
            self.controller.statusBar().showMessage("Filters cleared", 2000)

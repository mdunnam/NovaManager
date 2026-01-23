"""
Filters tab extracted from the monolithic main window.
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
    QMessageBox,
)


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

        # Status filters
        scroll_layout.addWidget(QLabel("<b>Status:</b>"))
        self.filter_raw = QCheckBox("Raw")
        scroll_layout.addWidget(self.filter_raw)
        self.filter_needs_edit = QCheckBox("Needs Edit")
        scroll_layout.addWidget(self.filter_needs_edit)
        self.filter_ready = QCheckBox("Ready for Release")
        scroll_layout.addWidget(self.filter_ready)
        self.filter_released = QCheckBox("Released")
        scroll_layout.addWidget(self.filter_released)

        # Quick filters
        scroll_layout.addWidget(QLabel("<b>Quick Filters:</b>"))
        self.filter_unknowns = QCheckBox("Show only 'unknown' values")
        self.filter_unknowns.setToolTip("Show photos with any field marked as 'unknown' by AI")
        scroll_layout.addWidget(self.filter_unknowns)

        # Platform filters
        scroll_layout.addWidget(QLabel("<b>Released Platforms:</b>"))
        self.filter_ig = QCheckBox("Released to Instagram")
        scroll_layout.addWidget(self.filter_ig)
        self.filter_tiktok = QCheckBox("Released to TikTok")
        scroll_layout.addWidget(self.filter_tiktok)
        self.filter_fansly = QCheckBox("Released to Fansly")
        scroll_layout.addWidget(self.filter_fansly)

        # Type of shot filter
        scroll_layout.addWidget(QLabel("<b>Type of Shot:</b>"))
        self.filter_type = QComboBox()
        self.filter_type.addItems(["(Any)", "selfie", "portrait", "fullbody", "closeup"])
        self.filter_type.setEditable(True)
        scroll_layout.addWidget(self.filter_type)

        # Pose filter
        scroll_layout.addWidget(QLabel("<b>Pose:</b>"))
        self.filter_pose = QComboBox()
        self.filter_pose.addItems(["(Any)", "standing", "sitting", "lying", "kneeling", "leaning"])
        self.filter_pose.setEditable(True)
        scroll_layout.addWidget(self.filter_pose)

        # Facing direction filter
        scroll_layout.addWidget(QLabel("<b>Facing:</b>"))
        self.filter_facing = QComboBox()
        self.filter_facing.addItems(["(Any)", "camera", "up", "down", "left", "right", "away"])
        scroll_layout.addWidget(self.filter_facing)

        # Explicit level filter
        scroll_layout.addWidget(QLabel("<b>Explicit Level:</b>"))
        self.filter_level = QComboBox()
        self.filter_level.addItems(["(Any)", "sfw", "mild", "suggestive", "explicit"])
        scroll_layout.addWidget(self.filter_level)

        # Color filter
        scroll_layout.addWidget(QLabel("<b>Color:</b>"))
        self.filter_color = QLineEdit()
        self.filter_color.setPlaceholderText("Any color")
        scroll_layout.addWidget(self.filter_color)

        # Material filter
        scroll_layout.addWidget(QLabel("<b>Material:</b>"))
        self.filter_material = QLineEdit()
        self.filter_material.setPlaceholderText("Any material")
        scroll_layout.addWidget(self.filter_material)

        # Clothing type filter
        scroll_layout.addWidget(QLabel("<b>Clothing Type:</b>"))
        self.filter_clothing = QLineEdit()
        self.filter_clothing.setPlaceholderText("Any clothing")
        scroll_layout.addWidget(self.filter_clothing)

        # Footwear filter
        scroll_layout.addWidget(QLabel("<b>Footwear:</b>"))
        self.filter_footwear = QLineEdit()
        self.filter_footwear.setPlaceholderText("Any footwear")
        scroll_layout.addWidget(self.filter_footwear)

        # Location filter
        scroll_layout.addWidget(QLabel("<b>Location:</b>"))
        self.filter_location = QLineEdit()
        self.filter_location.setPlaceholderText("Any location")
        scroll_layout.addWidget(self.filter_location)

        # Package filter
        scroll_layout.addWidget(QLabel("<b>Package:</b>"))
        self.filter_package = QLineEdit()
        self.filter_package.setPlaceholderText("Any package")
        scroll_layout.addWidget(self.filter_package)

        # Face Match rating filter
        scroll_layout.addWidget(QLabel("<b>Face Match Rating:</b>"))
        self.filter_face_match = QComboBox()
        self.filter_face_match.addItems([
            "(Any)",
            "5 stars",
            "4-5 stars",
            "3-5 stars",
            "2-5 stars",
            "1-5 stars",
            "Unrated",
        ])
        scroll_layout.addWidget(self.filter_face_match)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # Filter buttons at bottom
        filter_buttons = QHBoxLayout()
        apply_filters_btn = QPushButton("Apply Filters")
        apply_filters_btn.clicked.connect(self.apply_filters)
        filter_buttons.addWidget(apply_filters_btn)

        clear_filters_btn = QPushButton("Clear Filters")
        clear_filters_btn.clicked.connect(self.clear_filters)
        filter_buttons.addWidget(clear_filters_btn)

        layout.addLayout(filter_buttons)

    def apply_filters(self):
        """Apply filters to photos."""
        if self.controller.statusBar():
            self.controller.statusBar().showMessage("Filters applied (feature not yet implemented)", 3000)

    def clear_filters(self):
        """Clear all filters."""
        self.filter_raw.setChecked(False)
        self.filter_needs_edit.setChecked(False)
        self.filter_ready.setChecked(False)
        self.filter_released.setChecked(False)
        self.filter_unknowns.setChecked(False)
        self.filter_ig.setChecked(False)
        self.filter_tiktok.setChecked(False)
        self.filter_fansly.setChecked(False)
        self.filter_type.setCurrentIndex(0)
        self.filter_pose.setCurrentIndex(0)
        self.filter_facing.setCurrentIndex(0)
        self.filter_level.setCurrentIndex(0)
        self.filter_color.clear()
        self.filter_material.clear()
        self.filter_clothing.clear()
        self.filter_footwear.clear()
        self.filter_location.clear()
        self.filter_package.clear()
        self.filter_face_match.setCurrentIndex(0)
        if self.controller.statusBar():
            self.controller.statusBar().showMessage("Filters cleared", 2000)

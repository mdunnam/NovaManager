"""
Gallery tab UI extracted from the monolithic main window.
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QScrollArea,
    QGridLayout,
    QSplitter,
    QLineEdit,
    QMessageBox,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap


class GalleryTab(QWidget):
    """Encapsulates the gallery grid and detail editor."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.current_gallery_photo_id = None
        self._build_ui()

    # UI builders
    def _build_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Sort by:"))
        self.gallery_sort = QComboBox()
        self.gallery_sort.addItems(["Date Created", "ID", "Type", "Status", "Package"])
        self.gallery_sort.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self.gallery_sort)

        toolbar.addWidget(QLabel("Size:"))
        self.gallery_size = QComboBox()
        self.gallery_size.addItems(["Small", "Medium", "Large"])
        self.gallery_size.setCurrentText("Medium")
        self.gallery_size.currentTextChanged.connect(self.refresh)
        toolbar.addWidget(self.gallery_size)

        toolbar.addStretch()
        refresh_gallery_btn = QPushButton("Refresh")
        refresh_gallery_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_gallery_btn)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.gallery_container = QWidget()
        self.gallery_grid = QGridLayout(self.gallery_container)
        self.gallery_grid.setSpacing(10)
        self.gallery_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self.gallery_container)
        splitter.addWidget(scroll)

        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_title = QLabel("<h3>Photo Details</h3>")
        details_layout.addWidget(details_title)

        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setMaximumWidth(350)
        details_scroll.setMinimumWidth(250)

        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)

        self.gallery_id_label = QLabel("Select a photo")
        self.gallery_filepath_label = QLabel("")
        self.gallery_filepath_label.setWordWrap(True)
        self.gallery_filepath_label.setStyleSheet("QLabel { font-size: 9px; }")

        form_layout.addWidget(QLabel("<b>ID:</b>"))
        form_layout.addWidget(self.gallery_id_label)
        form_layout.addWidget(QLabel("<b>Filepath:</b>"))
        form_layout.addWidget(self.gallery_filepath_label)

        self.gallery_type = QLineEdit()
        self.gallery_pose = QLineEdit()
        self.gallery_facing = QComboBox()
        self.gallery_facing.addItems(["camera", "up", "down", "left", "right", "away"])
        self.gallery_facing.setEditable(True)
        self.gallery_level = QLineEdit()
        self.gallery_color = QLineEdit()
        self.gallery_material = QLineEdit()
        self.gallery_clothing = QLineEdit()
        self.gallery_footwear = QLineEdit()
        self.gallery_location = QLineEdit()
        self.gallery_package = QLineEdit()
        self.gallery_tags = QLineEdit()
        self.gallery_tags.setPlaceholderText("Comma-separated tags")

        form_layout.addWidget(QLabel("<b>Type:</b>"))
        form_layout.addWidget(self.gallery_type)
        form_layout.addWidget(QLabel("<b>Pose:</b>"))
        form_layout.addWidget(self.gallery_pose)
        form_layout.addWidget(QLabel("<b>Facing:</b>"))
        form_layout.addWidget(self.gallery_facing)
        form_layout.addWidget(QLabel("<b>Level:</b>"))
        form_layout.addWidget(self.gallery_level)
        form_layout.addWidget(QLabel("<b>Color:</b>"))
        form_layout.addWidget(self.gallery_color)
        form_layout.addWidget(QLabel("<b>Material:</b>"))
        form_layout.addWidget(self.gallery_material)
        form_layout.addWidget(QLabel("<b>Clothing:</b>"))
        form_layout.addWidget(self.gallery_clothing)
        form_layout.addWidget(QLabel("<b>Footwear:</b>"))
        form_layout.addWidget(self.gallery_footwear)
        form_layout.addWidget(QLabel("<b>Location:</b>"))
        form_layout.addWidget(self.gallery_location)
        form_layout.addWidget(QLabel("<b>Package:</b>"))
        form_layout.addWidget(self.gallery_package)
        form_layout.addWidget(QLabel("<b>Tags:</b>"))
        form_layout.addWidget(self.gallery_tags)
        form_layout.addStretch()

        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self.save_details)
        form_layout.addWidget(save_btn)

        details_scroll.setWidget(form_widget)
        details_layout.addWidget(details_scroll)
        splitter.addWidget(details_widget)
        splitter.setSizes([1000, 300])
        layout.addWidget(splitter)

    # API used by MainWindow
    def refresh(self):
        photos = self.controller.db.get_all_photos()
        self.refresh_with_photos(photos)

    def refresh_with_photos(self, photos):
        while self.gallery_grid.count():
            item = self.gallery_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sort_by = self.gallery_sort.currentText()
        if sort_by == "Date Created":
            photos.sort(key=lambda p: p['date_created'] or '', reverse=True)
        elif sort_by == "ID":
            photos.sort(key=lambda p: p['id'])
        elif sort_by == "Type":
            photos.sort(key=lambda p: p['type_of_shot'] or '')
        elif sort_by == "Status":
            photos.sort(key=lambda p: p['status'] or '')
        elif sort_by == "Package":
            photos.sort(key=lambda p: p['package_name'] or '')

        size_map = {"Small": 150, "Medium": 200, "Large": 250}
        thumb_size = size_map[self.gallery_size.currentText()]
        columns = 5
        for idx, photo in enumerate(photos):
            row = idx // columns
            col = idx % columns
            thumb_widget = self._create_thumbnail(photo, thumb_size)
            self.gallery_grid.addWidget(thumb_widget, row, col)

    def _create_thumbnail(self, photo, size):
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        frame.setLineWidth(2)
        frame.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)

        img_label = QLabel()
        img_label.setObjectName("thumbnailCell")
        img_label.setFixedSize(size, size)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if photo['filepath'] and os.path.exists(photo['filepath']):
            pixmap = self.controller.get_cached_thumbnail(photo['filepath'], size)
            if pixmap and not pixmap.isNull():
                img_label.setPixmap(pixmap)
            else:
                img_label.setText("[No Preview]")
        else:
            img_label.setText("[Missing]")
        layout.addWidget(img_label)

        face_match = int(photo.get('face_similarity') or 0)
        stars = "⭐" * face_match if face_match > 0 else ""
        info_text = f"ID: {photo['id']:06d}  {stars}\n"
        if photo['type_of_shot']:
            info_text += f"{photo['type_of_shot']}\n"
        if photo['status']:
            status_map = {'raw': 'Raw', 'needs_edit': 'Needs Edit', 'ready': 'Ready', 'released': 'Released'}
            info_text += status_map.get(photo['status'], photo['status'])

        info_label = QLabel(info_text)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("QLabel { font-size: 10px; }")
        layout.addWidget(info_label)

        frame.mousePressEvent = lambda event, fp=photo['filepath'], pid=photo['id']: self._handle_thumbnail_click(event, fp, pid)
        return frame

    def _handle_thumbnail_click(self, event, filepath, photo_id):
        try:
            if event.button() == Qt.MouseButton.MiddleButton:
                folder = os.path.dirname(filepath)
                if folder and os.path.isdir(folder):
                    os.startfile(folder)
                event.accept()
                return
            if event.button() == Qt.MouseButton.LeftButton:
                self.controller.show_full_image(filepath, photo_id)
                event.accept()
                return
        except Exception as exc:
            print(f"gallery thumbnail click error: {exc}")
        event.ignore()

    def show_details(self, photo):
        self.current_gallery_photo_id = photo['id']
        self.gallery_id_label.setText(f"{photo['id']:06d}")
        self.gallery_filepath_label.setText(photo['filepath'] or '')
        self.gallery_type.setText(photo['type_of_shot'] or '')
        self.gallery_pose.setText(photo['pose'] or '')
        self.gallery_facing.setCurrentText(photo['facing_direction'] or '')
        self.gallery_level.setText(photo['explicit_level'] or '')
        self.gallery_color.setText(photo['color_of_clothing'] or '')
        self.gallery_material.setText(photo['material'] or '')
        self.gallery_clothing.setText(photo['type_clothing'] or '')
        self.gallery_footwear.setText(photo['footwear'] or '')
        self.gallery_location.setText(photo['location'] or '')
        self.gallery_package.setText(photo['package_name'] or '')
        self.gallery_tags.setText(photo['tags'] or '')

    def save_details(self):
        if not self.current_gallery_photo_id:
            QMessageBox.warning(self, "No Photo Selected", "Please select a photo first")
            return

        photo = self.controller.db.get_photo(self.current_gallery_photo_id)
        if not photo:
            QMessageBox.warning(self, "Error", "Photo not found in database")
            return

        metadata = {
            'type_of_shot': self.gallery_type.text(),
            'pose': self.gallery_pose.text(),
            'facing_direction': self.gallery_facing.currentText(),
            'explicit_level': self.gallery_level.text(),
            'color_of_clothing': self.gallery_color.text(),
            'material': self.gallery_material.text(),
            'type_clothing': self.gallery_clothing.text(),
            'footwear': self.gallery_footwear.text(),
            'location': self.gallery_location.text(),
            'package_name': self.gallery_package.text(),
            'tags': self.gallery_tags.text()
        }

        ai_fields = ['type_of_shot', 'pose', 'facing_direction', 'explicit_level',
                     'color_of_clothing', 'material', 'type_clothing', 'footwear', 'location']

        for field in ai_fields:
            original_value = photo.get(field)
            new_value = metadata.get(field)
            if original_value and new_value and original_value != new_value:
                self.controller.db.save_correction(
                    self.current_gallery_photo_id,
                    field,
                    original_value,
                    new_value,
                )

        try:
            self.controller.db.update_photo_metadata(self.current_gallery_photo_id, metadata)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save: {exc}")
            return

        self.refresh()
        updated_photo = self.controller.db.get_photo(self.current_gallery_photo_id)
        if updated_photo:
            self.show_details(updated_photo)
        self.controller.refresh_tag_cloud()
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(
                f"Updated photo {self.current_gallery_photo_id:06d}", 3000
            )

    # Convenience for settings dialog
    def set_gallery_size(self, size_label: str):
        if size_label in [self.gallery_size.itemText(i) for i in range(self.gallery_size.count())]:
            self.gallery_size.setCurrentText(size_label)

    def get_gallery_size(self) -> str:
        return self.gallery_size.currentText()

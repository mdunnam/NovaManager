
"""
Nova Photo Manager - Main Application
A desktop application for managing and organizing Nova's photo collection
"""
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLineEdit, QLabel, 
                             QFileDialog, QCheckBox, QTableWidget, QTableWidgetItem,
                             QProgressBar, QMessageBox, QTabWidget, QTextEdit,
                             QComboBox, QHeaderView, QAbstractItemView, QInputDialog,
                             QStyledItemDelegate, QProgressDialog, QScrollArea, QGridLayout,
                             QFrame, QSplitter, QListWidget, QToolButton, QStyle,
                             QDialog, QDialogButtonBox, QGroupBox, QSpinBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSettings, QSize, QEvent
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QColor, QFont
from pathlib import Path
import os
import hashlib
import shutil

from ui.gallery_tab import GalleryTab
from ui.face_matching_tab import FaceMatchingTab
from ui.photos_tab import PhotosTab
from ui.publish_tab import PublishTab
from ui.filters_tab import FiltersTab
from ui.vocabularies_tab import VocabulariesTab
from ui.learning_tab import AILearningTab
from ui.instagram_tab import InstagramTab
from ui.tiktok_tab import TikTokTab

from database import PhotoDatabase
from ai_analyzer import analyze_image


class PhotoPickerDialog(QDialog):
    """Dialog for selecting a photo from the library in a gallery view"""
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Photo")
        self.setGeometry(200, 200, 1000, 700)
        self.db = db
        self.selected_photo = None
        self.init_ui()
    
    def _init_ui_legacy(self):
        """Initialize the picker UI"""
        layout = QVBoxLayout(self)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter by type, status, tags...")
        self.search_edit.textChanged.connect(self.refresh_gallery)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.gallery_container = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_container)
        self.gallery_layout.setSpacing(10)
        self.gallery_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self.gallery_container)
        layout.addWidget(scroll)

        button_row = QHBoxLayout()
        button_row.addStretch()
        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(select_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        self.refresh_gallery()

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
            from PyQt6.QtCore import QTimer
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
    
    def setModelData(self, editor, model, index):
        """Save the selected value back to the model"""
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


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
            # Get all image files
            image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
            
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
            
            total = len(files)
            
            import time
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
                    if existing and existing.get('type_of_shot'):
                        continue  # Skip already analyzed
                    
                    # Analyze image with AI
                    metadata = analyze_image(filepath, db)
                    
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
            import time
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
                    print(f"Re-analyzing photo ID {photo.get('id')}, filepath: {filepath}")
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
                    import traceback
                    error_details = traceback.format_exc()
                    print(f"Error details:\n{error_details}")
                    self.error.emit(f"Error analyzing {filename}: {str(e)}")
            
            self.finished.emit()
        
        except Exception as e:
            self.error.emit(str(e))
        finally:
            db.close()
    
    def stop(self):
        """Stop the reanalyzer thread"""
        self._is_running = False
    
    def run(self):
        """Analyze all images in the folder"""
        # Create a new database connection for this thread
        db = PhotoDatabase(self.db_path)
        
        try:
            # Get all image files
            image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
            
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
            
            total = len(files)
            
            import time
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
                    if existing and existing.get('type_of_shot'):
                        continue  # Skip already analyzed
                    
                    # Analyze image with AI (pass db for learning from corrections)
                    metadata = analyze_image(filepath, db)
                    
                    # Add or update in database
                    if existing:
                        # Protect user corrections - don't overwrite manually corrected fields
                        corrected_fields = db.get_corrected_fields_for_photo(existing['id'])
                        if corrected_fields:
                            for field in corrected_fields:
                                if field in metadata:
                                    print(f"    Preserving user correction for {field} on photo {existing['id']}")
                                    del metadata[field]
                        
                        if metadata:  # Only update if there are fields to update
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nova Photo Manager")
        self.resize(1200, 800)
        from PyQt6.QtCore import QSize, QSettings
        self.icon_size = QSize(24, 24)
        self.settings = QSettings()
        self.analyzer_thread = None
        self.db = PhotoDatabase()
        self.init_ui()
    # Library tab column indices - UPDATE THIS MAPPING IF COLUMNS CHANGE
    COL_CHECKBOX = 0
    COL_ID = 1
    COL_THUMBNAIL = 2
    COL_TYPE = 3
    COL_POSE = 4
    COL_FACING = 5
    COL_LEVEL = 6
    COL_COLOR = 7
    COL_MATERIAL = 8
    COL_CLOTHING = 9
    COL_FOOTWEAR = 10
    COL_LOCATION = 11
    COL_STATUS = 12
    COL_IG = 13
    COL_TIKTOK = 14
    COL_FANSLY = 15
    COL_PACKAGE = 16
    COL_TAGS = 17
    COL_DATE = 18
    COL_FILEPATH = 19
    COL_NOTES = 20

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
        print('Tab widget created', file=sys.stderr)
        try:
            self.gallery_tab = GalleryTab(self)
            self.tabs.addTab(self.gallery_tab, "Gallery")
            print('Gallery tab added', file=sys.stderr)
        except Exception as e:
            print(f'Error creating Gallery tab: {e}', file=sys.stderr)
        try:
            self.photos_tab = PhotosTab(self)
            self.tabs.addTab(self.photos_tab, "Library")
            print('Library tab added', file=sys.stderr)
        except Exception as e:
            print(f'Error creating Library tab: {e}', file=sys.stderr)
        try:
            self.filters_tab = FiltersTab(self)
            self.tabs.addTab(self.filters_tab, "Filters")
            print('Filters tab added', file=sys.stderr)
        except Exception as e:
            print(f'Error creating Filters tab: {e}', file=sys.stderr)
        try:
            self.vocabularies_tab = VocabulariesTab(self)
            self.tabs.addTab(self.vocabularies_tab, "Vocabularies")
            print('Vocabularies tab added', file=sys.stderr)
        except Exception as e:
            print(f'Error creating Vocabularies tab: {e}', file=sys.stderr)
        try:
            self.learning_tab = AILearningTab(self)
            self.tabs.addTab(self.learning_tab, "AI Learning")
            print('AI Learning tab added', file=sys.stderr)
        except Exception as e:
            print(f'Error creating AI Learning tab: {e}', file=sys.stderr)
        try:
            self.face_matching_tab = FaceMatchingTab(self)
            self.tabs.addTab(self.face_matching_tab, "Face Matching")
            print('Face Matching tab added', file=sys.stderr)
        except Exception as e:
            print(f'Error creating Face Matching tab: {e}', file=sys.stderr)
        try:
            self.publish_tab = PublishTab(self)
            self.tabs.addTab(self.publish_tab, "Publish")
            print('Publish tab added', file=sys.stderr)
        except Exception as e:
            print(f'Error creating Publish tab: {e}', file=sys.stderr)
        try:
            self.instagram_tab = InstagramTab(self)
            self.tabs.addTab(self.instagram_tab, "Instagram")
            print('Instagram tab added', file=sys.stderr)
        except Exception as e:
            print(f'Error creating Instagram tab: {e}', file=sys.stderr)
        try:
            self.tiktok_tab = TikTokTab(self)
            self.tabs.addTab(self.tiktok_tab, "TikTok")
            print('TikTok tab added', file=sys.stderr)
        except Exception as e:
            print(f'Error creating TikTok tab: {e}', file=sys.stderr)
        main_layout.addWidget(self.tabs)
        self.tabs.setCurrentIndex(0)

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
    
    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        # Top section - Folder selection and analysis
        top_section = self.create_top_section()
        main_layout.addWidget(top_section)
        # Tab widget for different views - already created in setup_ui()
        main_layout.addWidget(self.tabs)
        self.tabs.setCurrentIndex(0)
        
        # View Menu
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
        
        # Settings Menu
        settings_menu = self.menuBar().addMenu("&Settings")
        
        prefs_action = settings_menu.addAction("&Preferences")
        prefs_action.setShortcut("Ctrl+,")
        prefs_action.triggered.connect(self.show_settings_dialog)
        
        # Help Menu
        help_menu = self.menuBar().addMenu("&Help")
        
        about_action = help_menu.addAction("&About Nova Photo Manager")
        about_action.triggered.connect(self.show_about_dialog)
    
    def show_about_dialog(self):
        """Show an About dialog"""
        QMessageBox.information(
            self,
            "About Nova Photo Manager",
            "Nova Photo Manager v1.0\n\n"
            "A desktop application for managing and organizing photo collections.\n\n"
            "Features:\n"
            "• AI-powered photo analysis\n"
            "• Gallery and library views\n"
            "• Persistent notes with Lightbox viewer\n"
            "• Multi-platform release management\n"
            "• Advanced filtering and sorting\n\n"
            "© 2025 Nova Photo Manager"
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
        
        db_path_label = QLabel(f"Database: H:\\NovaApp\\nova_photos.db")
        db_path_label.setStyleSheet("color: gray; font-size: 9px;")
        info_layout.addWidget(db_path_label)
        
        cache_path_label = QLabel(f"Thumbnail Cache: {self.cache_dir}")
        cache_path_label.setStyleSheet("color: gray; font-size: 9px;")
        info_layout.addWidget(cache_path_label)
        
        clear_cache_btn = QPushButton("Clear Thumbnail Cache")
        clear_cache_btn.clicked.connect(self.clear_thumbnail_cache)
        info_layout.addWidget(clear_cache_btn)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(lambda: self.apply_settings(dialog, gallery_size_combo.currentText(), theme_combo.currentText()))
        cancel_btn = QPushButton("Cancel")
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
        browse_btn.clicked.connect(self.browse_folder)
        folder_row.addWidget(browse_btn)
        
        layout.addLayout(folder_row)
        
        # Options row
        options_row = QHBoxLayout()
        self.subfolder_checkbox = QCheckBox("Include Subfolders")
        self.subfolder_checkbox.setChecked(True)
        options_row.addWidget(self.subfolder_checkbox)
        options_row.addStretch()
        
        self.analyze_btn = QPushButton("Analyze Images")
        self.analyze_btn.clicked.connect(self.start_analysis)
        options_row.addWidget(self.analyze_btn)
        
        self.cancel_btn = QPushButton("Cancel Analysis")
        self.cancel_btn.clicked.connect(self.cancel_analysis)
        self.cancel_btn.setEnabled(False)
        options_row.addWidget(self.cancel_btn)
        
        layout.addLayout(options_row)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        return widget
    
    def create_photos_tab(self):
        """Return the shared photos tab widget."""
        return self.photos_tab
        
        reanalyze_btn = QPushButton()
        reanalyze_btn.setIcon(self.get_icon("reanalyze.png", "AI"))
        reanalyze_btn.setIconSize(self.icon_size)
        reanalyze_btn.setToolTip("Re-analyze selected photos with AI")
        reanalyze_btn.clicked.connect(self.reanalyze_selected)
        toolbar.addWidget(reanalyze_btn)
        
        train_ai_btn = QPushButton()
        train_ai_btn.setIcon(self.get_icon("train.png", "T"))
        train_ai_btn.setIconSize(self.icon_size)
        train_ai_btn.setToolTip("Train AI: Re-analyze using learned corrections")
        train_ai_btn.clicked.connect(self.reanalyze_selected)
        toolbar.addWidget(train_ai_btn)
        
        toolbar.addStretch()
        
        # Batch actions
        toolbar.addWidget(QLabel("Batch Actions:"))
        self.batch_package = QLineEdit()
        self.batch_package.setPlaceholderText("Package name...")
        self.batch_package.setMaximumWidth(200)
        toolbar.addWidget(self.batch_package)
        
        apply_package_btn = QPushButton("Set Package")
        apply_package_btn.clicked.connect(self.apply_package)
        toolbar.addWidget(apply_package_btn)
        
        toolbar.addStretch()
        
        # Thumbnail size toggle
        self.thumbnail_sizes = {'off': 0, 'small': 50, 'medium': 100, 'large': 150}
        self.current_thumb_size = 'medium'
        self.thumb_btn = QPushButton(f"Thumbnails: {self.current_thumb_size.title()}")
        self.thumb_btn.clicked.connect(self.toggle_thumbnail_size)
        toolbar.addWidget(self.thumb_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.photo_table = QTableWidget()
        self.photo_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.photo_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.photo_table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        
        # Set columns (checkbox column 0 left intentionally blank for a master checkbox later)
        columns = [
            "", "ID", "Thumbnail", "Type", "Pose", "Facing", "Level", "Color", 
            "Material", "Clothing", "Footwear", "Location", "Status",
            "IG", "TikTok", "Fansly", "Package", "Tags", "Date Created", "Filepath", "Notes"
        ]
        self.photo_table.setColumnCount(len(columns))
        self.photo_table.setHorizontalHeaderLabels(columns)
        self.photo_table.setColumnWidth(0, 30)  # Checkbox column narrow
        self.photo_table.setRowHeight(0, self.thumbnail_sizes[self.current_thumb_size])
        self.photo_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.photo_table.setSortingEnabled(True)
        
        # Enable editing for checkboxes
        self.photo_table.itemChanged.connect(self.on_table_item_changed)
        # Open package folder on double-click
        self.photo_table.cellDoubleClicked.connect(self.on_table_cell_double_clicked)
        # Debug: log clicks to trace column/index issues
        self.photo_table.cellClicked.connect(self.debug_log_cell_click)
        # Notes pane removed from main UI; no row-click notes loader
        # Enable middle-click handling on the table viewport (e.g., open file location from thumbnail)
        self.photo_table.viewport().installEventFilter(self)
        
        layout.addWidget(self.photo_table)
        
        # Bottom toolbar with status dropdown
        bottom_toolbar = QHBoxLayout()
        
        # Selection controls
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_photos)
        bottom_toolbar.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all_photos)
        bottom_toolbar.addWidget(deselect_all_btn)
        
        bottom_toolbar.addStretch()
        
        # Bulk edit button
        bulk_edit_btn = QPushButton("Bulk Edit Cells")
        bulk_edit_btn.clicked.connect(self.bulk_edit_cells)
        bottom_toolbar.addWidget(bulk_edit_btn)
        
        bottom_toolbar.addWidget(QLabel("Set Status for Selected:"))
        
        self.status_dropdown = QComboBox()
        self.status_dropdown.addItems(["Raw", "Needs Edit", "Ready for Release", "Released"])
        bottom_toolbar.addWidget(self.status_dropdown)
        
        apply_status_btn = QPushButton("Apply Status")
        apply_status_btn.clicked.connect(self.apply_status_to_selected)
        bottom_toolbar.addWidget(apply_status_btn)
        
        bottom_toolbar.addStretch()
        
        # Staged platform toggles
        bottom_toolbar.addWidget(QLabel("Toggle Staged:"))

        staged_ig = QPushButton()
        staged_ig.setIcon(self.get_icon("instagram.png", "IG"))
        staged_ig.setIconSize(self.icon_size)
        staged_ig.setToolTip("Stage to Instagram")
        staged_ig.clicked.connect(lambda: self.toggle_staged("instagram"))
        bottom_toolbar.addWidget(staged_ig)

        staged_tiktok = QPushButton()
        staged_tiktok.setIcon(self.get_icon("tiktok.png", "TT"))
        staged_tiktok.setIconSize(self.icon_size)
        staged_tiktok.setToolTip("Stage to TikTok")
        staged_tiktok.clicked.connect(lambda: self.toggle_staged("tiktok"))
        bottom_toolbar.addWidget(staged_tiktok)

        staged_fansly = QPushButton()
        staged_fansly.setIcon(self.get_icon("fansly.png", "F"))
        staged_fansly.setIconSize(self.icon_size)
        staged_fansly.setToolTip("Stage to Fansly")
        staged_fansly.clicked.connect(lambda: self.toggle_staged("fansly"))
        bottom_toolbar.addWidget(staged_fansly)

        # Unstage button (move back to root/<package>)
        unstage_btn = QPushButton()
        unstage_btn.setIcon(self.get_icon("unstage.png", "US"))
        unstage_btn.setIconSize(self.icon_size)
        unstage_btn.setToolTip("Unstage: move selected photos back to root/<package>")
        unstage_btn.clicked.connect(self.unstage_selected)
        bottom_toolbar.addWidget(unstage_btn)

        # Package and Unpackage controls grouped
        package_btn = QPushButton()
        package_btn.setIcon(self.get_icon("package.png", "PK"))
        package_btn.setIconSize(self.icon_size)
        package_btn.setToolTip("Manage packages for selected photos")
        package_btn.clicked.connect(self.manage_packages_dialog)
        bottom_toolbar.addWidget(package_btn)

        unpackage_btn = QPushButton()
        unpackage_btn.setIcon(self.get_icon("unpackage.png", "UP"))
        unpackage_btn.setIconSize(self.icon_size)
        unpackage_btn.setToolTip("Unpackage: clear package and move files to root")
        unpackage_btn.clicked.connect(self.unpackage_selected)
        bottom_toolbar.addWidget(unpackage_btn)

        # Release platform toggles
        bottom_toolbar.addWidget(QLabel("Toggle Release:"))
        
        toggle_ig = QPushButton()
        toggle_ig.setIcon(self.get_icon("instagram.png", "IG"))
        toggle_ig.setIconSize(self.icon_size)
        toggle_ig.setToolTip("Release: Instagram")
        toggle_ig.clicked.connect(lambda: self.toggle_release_status("released_instagram"))
        bottom_toolbar.addWidget(toggle_ig)
        
        toggle_tiktok = QPushButton()
        toggle_tiktok.setIcon(self.get_icon("tiktok.png", "TT"))
        toggle_tiktok.setIconSize(self.icon_size)
        toggle_tiktok.setToolTip("Release: TikTok")
        toggle_tiktok.clicked.connect(lambda: self.toggle_release_status("released_tiktok"))
        bottom_toolbar.addWidget(toggle_tiktok)
        
        toggle_fansly = QPushButton()
        toggle_fansly.setIcon(self.get_icon("fansly.png", "F"))
        toggle_fansly.setIconSize(self.icon_size)
        toggle_fansly.setToolTip("Release: Fansly")
        toggle_fansly.clicked.connect(lambda: self.toggle_release_status("released_fansly"))
    def create_publish_tab(self):
        """Return the shared publish tab widget."""
        return self.publish_tab
    
    def create_instagram_tab(self):
        """Return the shared Instagram tab widget."""
        return self.instagram_tab
    
    def create_tiktok_tab(self):
        """Return the shared TikTok tab widget."""
        return self.tiktok_tab
    
    # Notes UI removed from main window; notes are managed in Lightbox and Library column
    
    def create_gallery_tab(self):
        """Return the shared gallery tab widget."""
        return self.gallery_tab
    
    def create_filters_tab(self):
        """Create filters and search tab"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        
        # Scroll area for filters
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Auth section
        auth_group = QGroupBox("Authentication")
        auth_group.setObjectName("igAuthGroup")
        auth_layout = QVBoxLayout()
        
        self.ig_status_label = QLabel("Status: Not connected")
        self.ig_status_label.setStyleSheet("color: red;")
        auth_layout.addWidget(self.ig_status_label)
        
        auth_button_layout = QHBoxLayout()
        self.ig_auth_btn = QPushButton("Connect Instagram Account")
        self.ig_auth_btn.clicked.connect(self.connect_instagram)
        auth_button_layout.addWidget(self.ig_auth_btn)
        
        self.ig_logout_btn = QPushButton("Disconnect")
        self.ig_logout_btn.setEnabled(False)
        self.ig_logout_btn.clicked.connect(self.disconnect_instagram)
        auth_button_layout.addWidget(self.ig_logout_btn)
        auth_button_layout.addStretch()
        auth_layout.addLayout(auth_button_layout)
        
        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)
        
        # Content type tabs (Post, Reel, Story, Highlights)
        self.ig_content_tabs = QTabWidget()
        
        # Post tab
        post_tab = self.create_instagram_post_tab()
        self.ig_content_tabs.addTab(post_tab, "📷 Post")
        
        # Reel tab
        reel_tab = self.create_instagram_reel_tab()
        self.ig_content_tabs.addTab(reel_tab, "🎬 Reel")
        
        # Story tab
        story_tab = self.create_instagram_story_tab()
        self.ig_content_tabs.addTab(story_tab, "📖 Story")
        
        # Highlights tab
        highlights_tab = self.create_instagram_highlights_tab()
        self.ig_content_tabs.addTab(highlights_tab, "⭐ Highlights")
        
        layout.addWidget(self.ig_content_tabs)
        
        return widget
    
    def create_instagram_post_tab(self):
        """Instagram Post tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Photo preview and selection
        preview_layout = QHBoxLayout()
        
        # Thumbnail preview
        self.ig_thumbnail_label = QLabel()
        self.ig_thumbnail_label.setObjectName("thumbnailPreview")
        self.ig_thumbnail_label.setFixedSize(200, 200)
        self.ig_thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ig_thumbnail_label.setText("No photo selected")
        preview_layout.addWidget(self.ig_thumbnail_label)
        
        # Info and buttons
        info_layout = QVBoxLayout()
        
        self.ig_photo_label = QLabel("No photo selected")
        self.ig_photo_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.ig_photo_label)
        
        browse_btn = QPushButton("📂 Browse Photos")
        browse_btn.clicked.connect(self.ig_select_photo)
        info_layout.addWidget(browse_btn)
        
        self.ig_lightbox_btn = QPushButton("🔍 View in Lightbox")
        self.ig_lightbox_btn.setEnabled(False)
        self.ig_lightbox_btn.clicked.connect(self.ig_view_lightbox)
        info_layout.addWidget(self.ig_lightbox_btn)
        
        info_layout.addStretch()
        preview_layout.addLayout(info_layout)
        
        layout.addLayout(preview_layout)
        
        # Caption
        layout.addWidget(QLabel("Caption:"))
        self.ig_caption_edit = QTextEdit()
        self.ig_caption_edit.setPlaceholderText("Enter caption (max 2,200 characters)...")
        self.ig_caption_edit.setMaximumHeight(100)
        layout.addWidget(self.ig_caption_edit)
        
        # Hashtags
        layout.addWidget(QLabel("Hashtags:"))
        self.ig_hashtags_edit = QLineEdit()
        self.ig_hashtags_edit.setPlaceholderText("Separate with spaces (e.g., #photo #instagram #content)")
        layout.addWidget(self.ig_hashtags_edit)
        
        # Post button
        button_layout = QHBoxLayout()
        self.ig_post_btn = QPushButton("📤 Post to Instagram")
        self.ig_post_btn.setEnabled(False)
        self.ig_post_btn.clicked.connect(self.post_to_instagram)
        button_layout.addWidget(self.ig_post_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        layout.addStretch()
        
        return widget
    
    def create_instagram_reel_tab(self):
        """Instagram Reel tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<b>Instagram Reels</b>"))
        layout.addWidget(QLabel("Coming soon: Video upload and Reel-specific features"))
        layout.addStretch()
        return widget
    
    def create_instagram_story_tab(self):
        """Instagram Story tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<b>Instagram Stories</b>"))
        layout.addWidget(QLabel("Coming soon: Story-specific formatting and ephemeral content"))
        layout.addStretch()
        return widget
    
    def create_instagram_highlights_tab(self):
        """Instagram Highlights tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("<b>Instagram Highlights</b>"))
        layout.addWidget(QLabel("Coming soon: Archive Stories as Highlights"))
        layout.addStretch()
        return widget
    
    def create_tiktok_tab(self):
        """Create TikTok posting tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Header
        header = QLabel("<h3>🎵 TikTok Direct Post</h3>")
        layout.addWidget(header)
        
        # Auth section
        auth_group = QGroupBox("Authentication")
        auth_group.setObjectName("ttAuthGroup")
        auth_layout = QVBoxLayout()
        
        self.tt_status_label = QLabel("Status: Not connected")
        self.tt_status_label.setStyleSheet("color: red;")
        auth_layout.addWidget(self.tt_status_label)
        
        auth_button_layout = QHBoxLayout()
        self.tt_auth_btn = QPushButton("Connect TikTok Account")
        self.tt_auth_btn.clicked.connect(self.connect_tiktok)
        auth_button_layout.addWidget(self.tt_auth_btn)
        
        self.tt_logout_btn = QPushButton("Disconnect")
        self.tt_logout_btn.setEnabled(False)
        self.tt_logout_btn.clicked.connect(self.disconnect_tiktok)
        auth_button_layout.addWidget(self.tt_logout_btn)
        auth_button_layout.addStretch()
        auth_layout.addLayout(auth_button_layout)
        
        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)
        
        # Post section
        post_group = QGroupBox("Create Post")
        post_layout = QVBoxLayout()
        
        # Photo/Video selection
        post_layout.addWidget(QLabel("Select Video or Photo:"))
        media_layout = QHBoxLayout()
        self.tt_media_label = QLabel("No media selected")
        media_layout.addWidget(self.tt_media_label)
        self.tt_browse_media_btn = QPushButton("Browse")
        self.tt_browse_media_btn.clicked.connect(self.tt_select_media)
        media_layout.addWidget(self.tt_browse_media_btn)
        post_layout.addLayout(media_layout)
        
        # Caption
        post_layout.addWidget(QLabel("Caption:"))
        self.tt_caption_edit = QTextEdit()
        self.tt_caption_edit.setPlaceholderText("Enter caption (max 2,200 characters)...")
        self.tt_caption_edit.setMaximumHeight(100)
        post_layout.addWidget(self.tt_caption_edit)
        
        # Hashtags
        post_layout.addWidget(QLabel("Hashtags:"))
        self.tt_hashtags_edit = QLineEdit()
        self.tt_hashtags_edit.setPlaceholderText("Separate with spaces (e.g., #foryou #viral #content)")
        post_layout.addWidget(self.tt_hashtags_edit)
        
        # Post button
        button_layout = QHBoxLayout()
        self.tt_post_btn = QPushButton("📤 Post to TikTok")
        self.tt_post_btn.setEnabled(False)
        self.tt_post_btn.clicked.connect(self.post_to_tiktok)
        button_layout.addWidget(self.tt_post_btn)
        button_layout.addStretch()
        post_layout.addLayout(button_layout)
        
        post_group.setLayout(post_layout)
        layout.addWidget(post_group)
        
        layout.addStretch()
        
        return widget
    
    # Instagram posting methods
    def connect_instagram(self):
        """Connect to Instagram account with credential verification"""
        # Get credentials from user
        username, ok = QInputDialog.getText(self, "Instagram Login", "Username:")
        if not ok or not username:
            return
        
        password, ok = QInputDialog.getText(self, "Instagram Login", "Password:", QLineEdit.EchoMode.Password)
        if not ok or not password:
            return
        
        # Show verification progress with Cancel button
        progress = QMessageBox(self)
        progress.setWindowTitle("Verifying Instagram Credentials")
        progress.setText("Testing login credentials...\nPlease wait.")
        progress.setStandardButtons(QMessageBox.StandardButton.Cancel)
        
        try:
            from instagrapi import Client
            
            # Test login
            client = Client()
            client.login(username, password)
            
            # If we get here, login was successful
            progress.close()
            
            # Store credentials in database (encrypted)
            creds = {"username": username, "password": password}
            if self.db.store_api_credentials("instagram", creds):
                self.ig_status_label.setText(f"Status: Connected as @{username}")
                self.ig_status_label.setStyleSheet("color: green;")
                self.ig_auth_btn.setEnabled(False)
                self.ig_logout_btn.setEnabled(True)
                self.ig_post_btn.setEnabled(True)
                self.statusBar().showMessage(f"✅ Instagram account connected: @{username}", 3000)
                QMessageBox.information(self, "Connected", f"Successfully connected to Instagram as @{username}!")
            else:
                QMessageBox.warning(self, "Error", "Failed to store credentials")
        except Exception as e:
            progress.close()
            error_msg = str(e)
            QMessageBox.critical(
                self,
                "Instagram Connection Failed",
                f"Failed to connect to Instagram:\n\n{error_msg}\n\n"
                f"Setup Requirements:\n"
                f"• Username: Your Instagram username (not email)\n"
                f"• Password: Your Instagram password\n\n"
                f"If 2FA is enabled:\n"
                f"• Go to Instagram Settings → Security → Authentication apps\n"
                f"• Generate an app-specific password\n"
                f"• Use that password instead\n\n"
                f"If still failing:\n"
                f"• Try logging in on your phone first to verify credentials\n"
                f"• Wait 24 hours if Instagram blocked automation\n"
                f"• Use Instagram's official Business API instead"
            )
    
    def disconnect_instagram(self):
        """Disconnect from Instagram"""
        if self.db.delete_api_credentials("instagram"):
            self.ig_status_label.setText("Status: Not connected")
            self.ig_status_label.setStyleSheet("color: red;")
            self.ig_auth_btn.setEnabled(True)
            self.ig_logout_btn.setEnabled(False)
            self.ig_post_btn.setEnabled(False)
            self.statusBar().showMessage("Instagram account disconnected", 2000)
    
    def ig_select_photo(self):
        """Select photo for Instagram post"""
        picker = PhotoPickerDialog(self.db, self)
        if picker.exec() == QDialog.DialogCode.Accepted and picker.selected_photo:
            photo = picker.selected_photo
            self.ig_selected_photo_id = photo['id']
            self.ig_photo_label.setText(f"📸 {photo['id']:06d} - {photo.get('type_of_shot', 'Photo')}")
            
            # Update thumbnail preview
            if photo.get('filepath') and os.path.exists(photo['filepath']):
                pixmap = self.get_cached_thumbnail(photo['filepath'], 200)
                if pixmap and not pixmap.isNull():
                    self.ig_thumbnail_label.setPixmap(pixmap)
                else:
                    self.ig_thumbnail_label.setText("[No Preview]")
            
            self.ig_lightbox_btn.setEnabled(True)
            self.ig_post_btn.setEnabled(True)
            self.statusBar().showMessage(f"Photo selected: {photo['id']:06d}", 2000)
    
    def ig_view_lightbox(self):
        """View selected photo in lightbox"""
        if hasattr(self, 'ig_selected_photo_id'):
            photo = self.db.get_photo(self.ig_selected_photo_id)
            if photo and photo.get('filepath'):
                self.show_full_image(photo['filepath'], photo['id'])
    
    def post_to_instagram(self):
        """Actually post to Instagram using instagrapi"""
        if not hasattr(self, 'ig_selected_photo_id'):
            QMessageBox.warning(self, "Error", "Please select a photo first")
            return
        
        caption = self.ig_caption_edit.toPlainText()
        hashtags = self.ig_hashtags_edit.text()
        full_caption = f"{caption}\n\n{hashtags}".strip()
        
        if len(full_caption) > 2200:
            QMessageBox.warning(self, "Error", f"Caption too long: {len(full_caption)}/2200 characters")
            return
        
        photo = self.db.get_photo(self.ig_selected_photo_id)
        if not photo or not photo.get('filepath') or not os.path.exists(photo['filepath']):
            QMessageBox.warning(self, "Error", "Photo file not found")
            return
        
        # Show progress dialog with Cancel button
        progress = QMessageBox(self)
        progress.setWindowTitle("Posting to Instagram")
        progress.setText("Uploading to Instagram...\nPlease wait, this may take a minute.")
        progress.setStandardButtons(QMessageBox.StandardButton.Cancel)
        progress.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        
        try:
            from instagrapi import Client
            
            # Get stored credentials
            creds = self.db.get_api_credentials("instagram")
            if not creds:
                progress.close()
                raise Exception("Instagram credentials not found. Please reconnect.")
            
            username = creds.get("username")
            password = creds.get("password")
            
            # Show the progress dialog
            progress.show()
            QApplication.processEvents()
            
            # Login and upload
            client = Client()
            client.login(username, password)
            
            # Upload photo
            media = client.photo_upload(photo['filepath'], caption=full_caption)
            
            # Log the post
            post_url = f"https://instagram.com/p/{media.id}/"
            self.db.log_post(
                photo_id=self.ig_selected_photo_id,
                platform="instagram",
                post_type="post",
                caption=full_caption,
                post_url=post_url,
                post_id=str(media.id),
                status="success"
            )
            
            # Close progress and show success
            if progress.isVisible():
                progress.close()
            
            QMessageBox.information(
                self, 
                "Posted Successfully!", 
                f"Photo posted to Instagram!\n\nURL: {post_url}"
            )
            
            # Clear form
            self.ig_caption_edit.clear()
            self.ig_hashtags_edit.clear()
            self.statusBar().showMessage("Successfully posted to Instagram!", 3000)
            
        except Exception as e:
            error_msg = str(e)
            
            # Close progress and show error
            if progress.isVisible():
                progress.close()
            
            # Log the failed post
            self.db.log_post(
                photo_id=self.ig_selected_photo_id,
                platform="instagram",
                post_type="post",
                caption=full_caption,
                status="failed",
                error_msg=error_msg
            )
            
            QMessageBox.critical(
                self,
                "Instagram Upload Failed",
                f"Error uploading to Instagram:\n\n{error_msg}\n\n"
                f"Common issues:\n"
                f"• Wrong username or password\n"
                f"• Two-factor authentication enabled\n"
                f"• Instagram flagged suspicious activity\n"
                f"• Rate limit exceeded"
            )
    
    # TikTok posting methods
    def connect_tiktok(self):
        """Connect to TikTok account"""
        # Get credentials from user
        username, ok = QInputDialog.getText(self, "TikTok Login", "Username:")
        if not ok or not username:
            return
        
        password, ok = QInputDialog.getText(self, "TikTok Login", "Password:", QLineEdit.EchoMode.Password)
        if not ok or not password:
            return
        
        try:
            # Store credentials in database (encrypted)
            creds = {"username": username, "password": password}
            if self.db.store_api_credentials("tiktok", creds):
                self.tt_status_label.setText(f"Status: Connected as @{username}")
                self.tt_status_label.setStyleSheet("color: green;")
                self.tt_auth_btn.setEnabled(False)
                self.tt_logout_btn.setEnabled(True)
                self.tt_post_btn.setEnabled(True)
                self.statusBar().showMessage(f"TikTok account connected: @{username}", 3000)
            else:
                QMessageBox.warning(self, "Error", "Failed to store credentials")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Connection failed: {e}")
    
    def disconnect_tiktok(self):
        """Disconnect from TikTok"""
        if self.db.delete_api_credentials("tiktok"):
            self.tt_status_label.setText("Status: Not connected")
            self.tt_status_label.setStyleSheet("color: red;")
            self.tt_auth_btn.setEnabled(True)
            self.tt_logout_btn.setEnabled(False)
            self.tt_post_btn.setEnabled(False)
            self.statusBar().showMessage("TikTok account disconnected", 2000)
    
    def tt_select_media(self):
        """Select media for TikTok post"""
        picker = PhotoPickerDialog(self.db, self)
        if picker.exec() == QDialog.DialogCode.Accepted and picker.selected_photo:
            photo = picker.selected_photo
            self.tt_selected_media_id = photo['id']
            self.tt_media_label.setText(f"🎬 {photo['id']:06d} - {photo.get('type_of_shot', 'Media')}")
            self.statusBar().showMessage(f"Media selected: {photo['id']:06d}", 2000)
    
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
        
        QMessageBox.information(self, "Posted", 
            f"Media {self.tt_selected_media_id:06d} posted to TikTok!\n"
            f"Caption: {full_caption[:50]}...")
        # TODO: Implement actual posting via TikTok API
    
    def check_api_credentials(self):
        """Check for saved API credentials and restore UI state"""
        try:
            # Check Instagram
            if self.db.has_api_credentials("instagram"):
                creds = self.db.get_api_credentials("instagram")
                username = creds.get("username", "Unknown")
                self.ig_status_label.setText(f"Status: Connected as @{username}")
                self.ig_status_label.setStyleSheet("color: green;")
                self.ig_auth_btn.setEnabled(False)
                self.ig_logout_btn.setEnabled(True)
                self.ig_post_btn.setEnabled(True)
            
            # Check TikTok
            if self.db.has_api_credentials("tiktok"):
                creds = self.db.get_api_credentials("tiktok")
                username = creds.get("username", "Unknown")
                self.tt_status_label.setText(f"Status: Connected as @{username}")
                self.tt_status_label.setStyleSheet("color: green;")
                self.tt_auth_btn.setEnabled(False)
                self.tt_logout_btn.setEnabled(True)
                self.tt_post_btn.setEnabled(True)
        except Exception as e:
            print(f"Error checking credentials: {e}")
    
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
    
    # Notes UI removed from main window; notes are managed in Lightbox and Library column
    
    def create_gallery_tab(self):
        """Return the shared gallery tab widget."""
        return self.gallery_tab
    
    def create_filters_tab(self):
        """Create filters and search tab"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        
        # Scroll area for filters
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        layout = QVBoxLayout(scroll_widget)
        
        # Status filters
        layout.addWidget(QLabel("<b>Status:</b>"))
        self.filter_raw = QCheckBox("Raw")
        layout.addWidget(self.filter_raw)
        self.filter_needs_edit = QCheckBox("Needs Edit")
        layout.addWidget(self.filter_needs_edit)
        self.filter_ready = QCheckBox("Ready for Release")
        layout.addWidget(self.filter_ready)
        self.filter_released = QCheckBox("Released")
        layout.addWidget(self.filter_released)
        
        # Unknown values filter (for AI-flagged items)
        layout.addWidget(QLabel("<b>Quick Filters:</b>"))
        self.filter_unknowns = QCheckBox("Show only 'unknown' values")
        self.filter_unknowns.setToolTip("Show photos with any field marked as 'unknown' by AI")
        layout.addWidget(self.filter_unknowns)
        
        # Platform filters
        layout.addWidget(QLabel("<b>Released Platforms:</b>"))
        self.filter_ig = QCheckBox("Released to Instagram")
        layout.addWidget(self.filter_ig)
        self.filter_tiktok = QCheckBox("Released to TikTok")
        layout.addWidget(self.filter_tiktok)
        self.filter_fansly = QCheckBox("Released to Fansly")
        layout.addWidget(self.filter_fansly)
        
        # Type of shot filter
        layout.addWidget(QLabel("<b>Type of Shot:</b>"))
        self.filter_type = QComboBox()
        self.filter_type.addItems(["(Any)", "selfie", "portrait", "fullbody", "closeup"])
        self.filter_type.setEditable(True)
        layout.addWidget(self.filter_type)
        
        # Pose filter
        layout.addWidget(QLabel("<b>Pose:</b>"))
        self.filter_pose = QComboBox()
        self.filter_pose.addItems(["(Any)", "standing", "sitting", "lying", "kneeling", "leaning"])
        self.filter_pose.setEditable(True)
        layout.addWidget(self.filter_pose)
        
        # Facing direction filter
        layout.addWidget(QLabel("<b>Facing:</b>"))
        self.filter_facing = QComboBox()
        self.filter_facing.addItems(["(Any)", "camera", "up", "down", "left", "right", "away"])
        layout.addWidget(self.filter_facing)
        
        # Explicit level filter
        layout.addWidget(QLabel("<b>Explicit Level:</b>"))
        self.filter_level = QComboBox()
        self.filter_level.addItems(["(Any)", "sfw", "mild", "suggestive", "explicit"])
        layout.addWidget(self.filter_level)
        
        # Color filter
        layout.addWidget(QLabel("<b>Color:</b>"))
        self.filter_color = QLineEdit()
        self.filter_color.setPlaceholderText("Any color")
        layout.addWidget(self.filter_color)
        
        # Material filter
        layout.addWidget(QLabel("<b>Material:</b>"))
        self.filter_material = QLineEdit()
        self.filter_material.setPlaceholderText("Any material")
        layout.addWidget(self.filter_material)
        
        # Clothing type filter
        layout.addWidget(QLabel("<b>Clothing Type:</b>"))
        self.filter_clothing = QLineEdit()
        self.filter_clothing.setPlaceholderText("Any clothing")
        layout.addWidget(self.filter_clothing)
        
        # Footwear filter
        layout.addWidget(QLabel("<b>Footwear:</b>"))
        self.filter_footwear = QLineEdit()
        self.filter_footwear.setPlaceholderText("Any footwear")
        layout.addWidget(self.filter_footwear)
        
        # Location filter
        layout.addWidget(QLabel("<b>Location:</b>"))
        self.filter_location = QLineEdit()
        self.filter_location.setPlaceholderText("Any location")
        layout.addWidget(self.filter_location)
        
        # Package filter
        layout.addWidget(QLabel("<b>Package:</b>"))
        self.filter_package = QLineEdit()
        self.filter_package.setPlaceholderText("Any package")
        layout.addWidget(self.filter_package)

        # Face Match rating filter
        layout.addWidget(QLabel("<b>Face Match Rating:</b>"))
        self.filter_face_match = QComboBox()
        self.filter_face_match.addItems([
            "(Any)",
            "5 stars",
            "4-5 stars",
            "3-5 stars",
            "2-5 stars",
            "1-5 stars",
            "Unrated"
        ])
        layout.addWidget(self.filter_face_match)
        
        layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        
        # Filter buttons at bottom
        filter_buttons = QHBoxLayout()
        apply_filters_btn = QPushButton("Apply Filters")
        apply_filters_btn.clicked.connect(self.apply_filters)
        filter_buttons.addWidget(apply_filters_btn)
        
        clear_filters_btn = QPushButton("Clear Filters")
        clear_filters_btn.clicked.connect(self.clear_filters)
        filter_buttons.addWidget(clear_filters_btn)
        
        main_layout.addLayout(filter_buttons)
        
        return widget
    
    def create_vocabulary_tab(self):
        """Return the shared vocabularies tab widget."""
        return self.vocabularies_tab
    
    def create_learning_tab(self):
        """Return the shared AI learning tab widget."""
        return self.learning_tab
    
    def create_face_matching_tab(self):
        
        info = QLabel("Manage allowed values for each field. AI will only use these values - unknowns will be flagged.")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Field selector
        field_layout = QHBoxLayout()
        field_layout.addWidget(QLabel("Field:"))
        self.vocab_field_selector = QComboBox()
        self.vocab_field_selector.addItems([
            'type_of_shot', 'pose', 'facing_direction', 'explicit_level',
            'color_of_clothing', 'material', 'type_clothing', 'footwear',
            'interior_exterior', 'location'
        ])
        self.vocab_field_selector.currentTextChanged.connect(self.load_vocabulary_for_field)
        field_layout.addWidget(self.vocab_field_selector)
        field_layout.addStretch()
        layout.addLayout(field_layout)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.vocab_input = QLineEdit()
        self.vocab_input.setPlaceholderText("Enter new value...")
        toolbar.addWidget(self.vocab_input)
        
        add_btn = QPushButton("Add Value")
        add_btn.clicked.connect(self.add_vocabulary_value)
        toolbar.addWidget(add_btn)
        
        rename_btn = QPushButton("Rename Selected")
        rename_btn.clicked.connect(self.rename_vocabulary_value)
        toolbar.addWidget(rename_btn)
        
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_vocabulary_value)
        toolbar.addWidget(delete_btn)
        
        cleanup_btn = QPushButton("Clean Unused")
        cleanup_btn.clicked.connect(self.cleanup_vocabulary)
        toolbar.addWidget(cleanup_btn)
        
        layout.addLayout(toolbar)
        
        # List widget for vocabulary values
        self.vocab_list = QTableWidget()
        self.vocab_list.setColumnCount(3)
        self.vocab_list.setHorizontalHeaderLabels(["Value", "Description", "Usage Count"])
        self.vocab_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.vocab_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.vocab_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.vocab_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.vocab_list.itemChanged.connect(self.on_vocab_description_changed)
        layout.addWidget(self.vocab_list)
        
        # Load initial vocabulary
        self.load_vocabulary_for_field(self.vocab_field_selector.currentText())
        
        return widget
    
    def create_learning_tab(self):
        """Create AI Learning tab to show what the AI has learned"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Info label
        info = QLabel("This shows the patterns AI has learned from your corrections.\n"
                     "The more you correct, the smarter it gets!")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Learning Data")
        refresh_btn.clicked.connect(self.refresh_learning_data)
        layout.addWidget(refresh_btn)
        
        # Table to show corrections
        self.learning_table = QTableWidget()
        self.learning_table.setColumnCount(5)
        self.learning_table.setHorizontalHeaderLabels(["Field", "AI Said", "You Corrected To", "Times", "Last Correction"])
        self.learning_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.learning_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.learning_table.setSortingEnabled(True)
        layout.addWidget(self.learning_table)
        
        # Backup/Restore buttons
        backup_layout = QHBoxLayout()
        
        backup_btn = QPushButton("📦 Backup Learning Data")
        backup_btn.clicked.connect(self.manual_backup_learning_data)
        backup_layout.addWidget(backup_btn)
        
        restore_btn = QPushButton("♻️ Restore from Backup")
        restore_btn.clicked.connect(self.restore_learning_data)
        backup_layout.addWidget(restore_btn)
        
        layout.addLayout(backup_layout)
        
        # Clear learning button (with warning color)
        clear_btn = QPushButton("⚠️ Clear All Learning Data")
        clear_btn.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; font-weight: bold; }")
        clear_btn.clicked.connect(self.clear_learning_data)
        layout.addWidget(clear_btn)
        
        # Load initial data
        self.refresh_learning_data()
        
        return widget
    
    def create_face_matching_tab(self):
        """Return the shared face matching tab widget."""
        return self.face_matching_tab
        
        # Thumbnail grid of benchmark photos (persistent, no text labels)
        self.benchmark_scroll = QScrollArea()
        self.benchmark_scroll.setWidgetResizable(True)
        self.benchmark_container = QWidget()
        self.benchmark_grid = QGridLayout(self.benchmark_container)
        self.benchmark_grid.setContentsMargins(4, 4, 4, 4)
        self.benchmark_grid.setSpacing(8)
        self.benchmark_scroll.setWidget(self.benchmark_container)
        left_layout.addWidget(self.benchmark_scroll, 1)
        
        # Buttons for benchmark management
        benchmark_buttons = QHBoxLayout()
        add_benchmark_btn = QPushButton("Add Photos")
        add_benchmark_btn.clicked.connect(self.add_benchmark_photos)
        benchmark_buttons.addWidget(add_benchmark_btn)
        
        clear_benchmark_btn = QPushButton("Clear All")
        clear_benchmark_btn.clicked.connect(self.clear_benchmark_photos)
        benchmark_buttons.addWidget(clear_benchmark_btn)
        
        left_layout.addLayout(benchmark_buttons)
        
        # Run comparison button
        run_btn = QPushButton("🔍 Analyze All Photos")
        run_btn.clicked.connect(self.run_face_similarity_analysis)
        run_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        left_layout.addWidget(run_btn)
        
        content_layout.addWidget(left_widget, 1)
        
        # RIGHT SIDE: Log output (matching left side height)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        log_label = QLabel("<b>Analysis Log</b>")
        right_layout.addWidget(log_label)
        
        self.face_log_output = QTextEdit()
        self.face_log_output.setReadOnly(True)
        self.face_log_output.setFontFamily("Courier")
        self.face_log_output.setFontPointSize(8)
        self.face_log_output.setStyleSheet("background-color: #f5f5f5; color: #333;")
        right_layout.addWidget(self.face_log_output, 1)
        
        content_layout.addWidget(right_widget, 1)
        layout.addLayout(content_layout)
        
        # Filter and Results section
        results_label = QLabel("<b>Results:</b> (Filter photos by similarity rating)")
        layout.addWidget(results_label)
        
        # Filter by rating + actions
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Show photos rated:"))
        
        self.rating_filter = QComboBox()
        self.rating_filter.addItems(["All", "5 stars", "4-5 stars", "3-5 stars", "2-5 stars", "1-5 stars", "Unrated"])
        self.rating_filter.currentTextChanged.connect(self.apply_face_similarity_filter)
        filter_layout.addWidget(self.rating_filter)
        
        # Flag selected as button
        flag_btn = QPushButton("🚩 Flag Selected with Rating")
        flag_btn.clicked.connect(self.flag_selected_photos)
        filter_layout.addWidget(flag_btn)
        
        # Clear results button (also clears benchmarks)
        clear_results_btn = QPushButton("Clear Results")
        clear_results_btn.setToolTip("Reset face match ratings to unrated (0) and clear benchmark photos")
        clear_results_btn.clicked.connect(self.clear_face_similarity_results)
        filter_layout.addWidget(clear_results_btn)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)
        
        # Results table
        self.face_results_table = QTableWidget()
        self.face_results_table.setColumnCount(6)
        self.face_results_table.setHorizontalHeaderLabels(["ID", "Thumbnail", "Filename", "Rating", "Confidence", "Flag"])
        
        # Set column widths
        self.face_results_table.setColumnWidth(0, 40)      # ID
        self.face_results_table.setColumnWidth(1, 60)      # Thumbnail
        self.face_results_table.setColumnWidth(2, 250)     # Filename
        self.face_results_table.setColumnWidth(3, 80)      # Rating
        self.face_results_table.setColumnWidth(4, 100)     # Confidence
        self.face_results_table.setColumnWidth(5, 50)      # Flag checkbox
        
        self.face_results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.face_results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.face_results_table.setAlternatingRowColors(True)
        self.face_results_table.setSortingEnabled(True)
        self.face_results_table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.face_results_table.doubleClicked.connect(self.open_photo_from_face_results)
        layout.addWidget(self.face_results_table)
        
        # Initialize benchmark photos list (persistent)
        self.benchmark_photos = []
        self.load_benchmarks_from_settings()
        self.render_benchmark_grid()

        # Load persisted analysis results
        self.load_face_similarity_results()
        
        return widget
    
    def add_benchmark_photos(self):
        if hasattr(self, 'face_matching_tab') and self.face_matching_tab:
            self.face_matching_tab.add_benchmark_photos()

    def clear_benchmark_photos(self):
        if hasattr(self, 'face_matching_tab') and self.face_matching_tab:
            self.face_matching_tab.clear_benchmark_photos()

    def save_benchmarks_to_settings(self):
        if hasattr(self, 'face_matching_tab') and self.face_matching_tab:
            self.face_matching_tab.save_benchmarks_to_settings()

    def load_benchmarks_from_settings(self):
        if hasattr(self, 'face_matching_tab') and self.face_matching_tab:
            self.face_matching_tab.load_benchmarks_from_settings()

    def render_benchmark_grid(self):
        if hasattr(self, 'face_matching_tab') and self.face_matching_tab:
            self.face_matching_tab.render_benchmark_grid()

    def delete_benchmark_path(self, path):
        if hasattr(self, 'face_matching_tab') and self.face_matching_tab:
            self.face_matching_tab.delete_benchmark_path(path)

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
        return set(self.persistent_selected_ids)

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
                self.COL_TYPE: 'COL_TYPE',
                self.COL_POSE: 'COL_POSE',
                self.COL_FACING: 'COL_FACING',
                self.COL_LEVEL: 'COL_LEVEL',
                self.COL_COLOR: 'COL_COLOR',
                self.COL_MATERIAL: 'COL_MATERIAL',
                self.COL_CLOTHING: 'COL_CLOTHING',
                self.COL_FOOTWEAR: 'COL_FOOTWEAR',
                self.COL_LOCATION: 'COL_LOCATION',
                self.COL_STATUS: 'COL_STATUS',
                self.COL_IG: 'COL_IG',
                self.COL_TIKTOK: 'COL_TIKTOK',
                self.COL_FANSLY: 'COL_FANSLY',
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
            if obj is self.photo_table.viewport() and event.type() in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.MouseButtonDblClick,
            ):
                if event.button() == Qt.MouseButton.MiddleButton:
                    idx = self.photo_table.indexAt(event.pos())
                    if idx.isValid() and idx.column() == self.COL_THUMBNAIL:
                        row = idx.row()
                        fp_item = self.photo_table.item(row, self.COL_FILEPATH)
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

    def clear_face_similarity_results(self):
        """Clear all face match ratings (set to 0) and clear benchmark photos"""
        reply = QMessageBox.question(
            self,
            "Clear Face Match Results",
            "This will reset face match ratings to unrated (0) for all photos and clear benchmark photos. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        photos = self.db.get_all_photos()
        for p in photos:
            self.db.update_photo_metadata(p['id'], {'face_similarity': 0})
        
        # Also clear benchmark photos
        self.clear_benchmark_photos()
        
        self.load_face_similarity_results()
        self.statusBar().showMessage("Cleared face match results and benchmark photos", 3000)
    
    def run_face_similarity_analysis(self):
        """Run face similarity analysis on all photos"""
        if not self.benchmark_photos:
            QMessageBox.warning(self, "No Benchmarks", "Please add 5-10 reference photos first!")
            return
        
        # Capture print output
        import io
        import sys
        
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = sys.stdout
        
        try:
            from deepface import DeepFace
            import numpy as np
        except ImportError:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Missing Library")
            msg.setText("<b>DeepFace is required for face matching!</b>")
            msg.setInformativeText("Run: pip install deepface")
            msg.exec()
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            return
        
        # Load benchmark embeddings
        self.statusBar().showMessage("Loading benchmark faces...", 0)
        QApplication.processEvents()
        
        self.face_log_output.clear()
        log_text = "=== Face Matching Analysis ===\n"
        self.face_log_output.setText(log_text)
        
        benchmark_embeddings = []
        for benchmark_path in self.benchmark_photos:
            try:
                log_text += f"Loading: {Path(benchmark_path).name}\n"
                self.face_log_output.setText(log_text)
                QApplication.processEvents()
                
                rep = DeepFace.represent(
                    img_path=benchmark_path,
                    model_name="ArcFace",
                    detector_backend="retinaface",
                    enforce_detection=False
                )
                if rep:
                    embedding = np.array(rep[0]["embedding"] if isinstance(rep, list) else rep["embedding"])
                    benchmark_embeddings.append(embedding)
                    log_text += f"✓ Loaded: {Path(benchmark_path).name}\n"
                else:
                    log_text += f"⚠ No face found: {Path(benchmark_path).name}\n"
                self.face_log_output.setText(log_text)
                self.face_log_output.verticalScrollBar().setValue(
                    self.face_log_output.verticalScrollBar().maximum()
                )
            except Exception as e:
                log_text += f"✗ Error: {Path(benchmark_path).name}: {str(e)[:50]}\n"
                self.face_log_output.setText(log_text)
                self.face_log_output.verticalScrollBar().setValue(
                    self.face_log_output.verticalScrollBar().maximum()
                )
        
        if not benchmark_embeddings:
            QMessageBox.critical(self, "No Faces Found", "Could not detect faces in any benchmark photos!")
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            return
        
        log_text += f"\nAnalyzing {len(self.db.get_all_photos())} library photos...\n"
        self.face_log_output.setText(log_text)
        QApplication.processEvents()
        
        # Get all photos
        photos = self.db.get_all_photos()
        
        # Progress dialog
        progress = QProgressDialog(f"Analyzing {len(photos)} photos...", "Cancel", 0, len(photos), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        
        # Analyze each photo
        for i, photo in enumerate(photos):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            progress.setLabelText(f"Analyzing {photo['filename']}...")
            QApplication.processEvents()
            
            try:
                rep = DeepFace.represent(
                    img_path=photo['filepath'],
                    model_name="ArcFace",
                    detector_backend="retinaface",
                    enforce_detection=False
                )
                if rep:
                    embedding = np.array(rep[0]["embedding"] if isinstance(rep, list) else rep["embedding"])
                    sims = []
                    for bench in benchmark_embeddings:
                        denom = (np.linalg.norm(embedding) * np.linalg.norm(bench))
                        sim = float(np.dot(embedding, bench) / denom) if denom > 0 else 0.0
                        sims.append(sim)
                    avg_sim = np.mean(sims) if sims else 0.0
                    
                    # Map similarity to 1-5 rating (higher similarity = higher rating)
                    if avg_sim >= 0.80:
                        rating = 5
                    elif avg_sim >= 0.70:
                        rating = 4
                    elif avg_sim >= 0.60:
                        rating = 3
                    elif avg_sim >= 0.50:
                        rating = 2
                    else:
                        rating = 1
                    
                    self.db.update_photo_metadata(photo['id'], {'face_similarity': rating})
                else:
                    self.db.update_photo_metadata(photo['id'], {'face_similarity': 0})
            
            except Exception as e:
                self.db.update_photo_metadata(photo['id'], {'face_similarity': 0})
        
        progress.setValue(len(photos))
        log_text += f"✓ Analysis complete!\n"
        self.face_log_output.setText(log_text)
        
        # Refresh results
        self.load_face_similarity_results()
        
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
        QMessageBox.information(self, "Analysis Complete", f"Analyzed {len(photos)} photos!\n\nUse the filter to view results.")
    
    def flag_selected_photos(self):
        """Flag selected photos with their confidence ratings to metadata"""
        selected_rows = self.face_results_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select photos to flag.")
            return
        
        # Get unique rows
        rows = set(index.row() for index in selected_rows)
        flagged_count = 0
        
        for row in rows:
            # Get photo ID from first column
            id_item = self.face_results_table.item(row, 0)
            if id_item:
                photo_id = int(id_item.text())
                # Get rating from stars column
                rating_item = self.face_results_table.item(row, 3)
                if rating_item:
                    rating = rating_item.text().count("⭐")
                    # Save to metadata
                    self.db.update_photo_metadata(photo_id, {'face_similarity': rating})
                    flagged_count += 1
        
        self.statusBar().showMessage(f"Flagged {flagged_count} photos with confidence ratings", 3000)
        QMessageBox.information(self, "Flagged", f"Successfully flagged {flagged_count} photo(s) with their confidence ratings!")

        """Run face similarity analysis on all photos"""
        if not self.benchmark_photos:
            QMessageBox.warning(self, "No Benchmarks", "Please add 5-10 reference photos first!")
            return
        
        if len(self.benchmark_photos) < 3:
            reply = QMessageBox.question(
                self,
                "Few Benchmarks",
                f"You only have {len(self.benchmark_photos)} benchmark photo(s). For best results, use 5-10 photos.\n\nContinue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        # Import DeepFace matcher
        try:
            from deepface import DeepFace
            import numpy as np
        except ImportError:
            QMessageBox.critical(
                self,
                "Missing Library",
                "DeepFace is required for face matching.\n\nRun: pip install deepface"
            )
            return
        
        # Load benchmark embeddings
        self.statusBar().showMessage("Loading benchmark faces...", 0)
        QApplication.processEvents()
        
        benchmark_embeddings = []
        for benchmark_path in self.benchmark_photos:
            try:
                rep = DeepFace.represent(
                    img_path=benchmark_path,
                    model_name="ArcFace",
                    detector_backend="retinaface",
                    enforce_detection=False
                )
                if rep:
                    embedding = np.array(rep[0]["embedding"] if isinstance(rep, list) else rep["embedding"])
                    benchmark_embeddings.append(embedding)
                    print(f"✓ Loaded face from: {Path(benchmark_path).name}")
                else:
                    print(f"⚠ No face found in benchmark: {Path(benchmark_path).name}")
            except Exception as e:
                print(f"✗ Error loading benchmark {Path(benchmark_path).name}: {e}")
        
        if not benchmark_embeddings:
            QMessageBox.critical(self, "No Faces Found", "Could not detect faces in any benchmark photos!")
            return
        
        # Get all photos
        photos = self.db.get_all_photos()
        
        # Progress dialog
        progress = QProgressDialog(f"Analyzing {len(photos)} photos...", "Cancel", 0, len(photos), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        
        # Analyze each photo
        for i, photo in enumerate(photos):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            progress.setLabelText(f"Analyzing {photo['filename']}...")
            QApplication.processEvents()
            
            try:
                rep = DeepFace.represent(
                    img_path=photo['filepath'],
                    model_name="ArcFace",
                    detector_backend="retinaface",
                    enforce_detection=False
                )
                if rep:
                    embedding = np.array(rep[0]["embedding"] if isinstance(rep, list) else rep["embedding"])
                    sims = []
                    for bench in benchmark_embeddings:
                        denom = (np.linalg.norm(embedding) * np.linalg.norm(bench))
                        sim = float(np.dot(embedding, bench) / denom) if denom > 0 else 0.0
                        sims.append(sim)
                    avg_sim = np.mean(sims) if sims else 0.0
                    
                    # Map similarity to 1-5 rating (higher similarity = higher rating)
                    if avg_sim >= 0.80:
                        rating = 5
                    elif avg_sim >= 0.70:
                        rating = 4
                    elif avg_sim >= 0.60:
                        rating = 3
                    elif avg_sim >= 0.50:
                        rating = 2
                    else:
                        rating = 1
                    
                    self.db.update_photo_metadata(photo['id'], {'face_similarity': rating})
                    print(f"Photo {photo['id']}: Rating {rating}/5 (similarity: {avg_sim:.3f})")
                else:
                    self.db.update_photo_metadata(photo['id'], {'face_similarity': 0})
            
            except Exception as e:
                print(f"Error analyzing {photo['filename']}: {e}")
                self.db.update_photo_metadata(photo['id'], {'face_similarity': 0})
        
        progress.setValue(len(photos))
        self.statusBar().showMessage("Face similarity analysis complete!", 3000)
        
        # Refresh results
        self.load_face_similarity_results()
        QMessageBox.information(self, "Analysis Complete", f"Analyzed {len(photos)} photos!\n\nUse the filter to view results.")
    
    def load_face_similarity_results(self):
        """Load face similarity results into table"""
        self.face_results_table.setRowCount(0)
        
        photos = self.db.get_all_photos()
        
        for photo in photos:
            rating = photo.get('face_similarity', 0)
            if rating > 0:  # Only show rated photos
                row = self.face_results_table.rowCount()
                self.face_results_table.insertRow(row)
                self.face_results_table.setRowHeight(row, 60)
                
                # ID
                id_item = QTableWidgetItem(str(photo['id']))
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.face_results_table.setItem(row, 0, id_item)
                
                # Thumbnail
                thumb_label = QLabel()
                thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                try:
                    from pathlib import Path
                    filepath = Path(photo['filepath'])
                    # Try thumbnail cache first
                    thumb_path = Path("H:\\NovaApp\\thumbnail_cache") / f"{filepath.stem}_thumb.jpg"
                    if not thumb_path.exists():
                        # Fall back to actual image file
                        thumb_path = filepath
                    
                    if thumb_path.exists():
                        pixmap = QPixmap(str(thumb_path)).scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        if not pixmap.isNull():
                            thumb_label.setPixmap(pixmap)
                except Exception as e:
                    print(f"Thumbnail error: {e}")
                
                self.face_results_table.setCellWidget(row, 1, thumb_label)
                
                # Filename
                filename_item = QTableWidgetItem(photo['filename'])
                filename_item.setFlags(filename_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.face_results_table.setItem(row, 2, filename_item)
                
                # Rating (stars)
                stars = "⭐" * rating
                rating_item = QTableWidgetItem(stars)
                rating_item.setFlags(rating_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                rating_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.face_results_table.setItem(row, 3, rating_item)
                
                # Confidence
                confidence = ["", "Low", "Fair", "Good", "Very Good", "Excellent"][rating]
                conf_item = QTableWidgetItem(confidence)
                conf_item.setFlags(conf_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                conf_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.face_results_table.setItem(row, 4, conf_item)
                
                # Flag checkbox
                flag_checkbox = QCheckBox()
                flag_checkbox.setProperty("photo_id", photo['id'])
                flag_cell = QTableWidgetItem()
                flag_cell.setFlags(flag_cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.face_results_table.setItem(row, 5, flag_cell)
                self.face_results_table.setCellWidget(row, 5, flag_checkbox)
    
    def apply_face_similarity_filter(self):
        """Filter results by rating"""
        filter_text = self.rating_filter.currentText()
        
        for row in range(self.face_results_table.rowCount()):
            rating_item = self.face_results_table.item(row, 3)
            if rating_item:
                star_count = rating_item.text().count("⭐")
                
                show = False
                if filter_text == "All":
                    show = True
                elif filter_text == "5 stars":
                    show = star_count == 5
                elif filter_text == "4-5 stars":
                    show = star_count >= 4
                elif filter_text == "3-5 stars":
                    show = star_count >= 3
                elif filter_text == "2-5 stars":
                    show = star_count >= 2
                elif filter_text == "1-5 stars":
                    show = star_count >= 1
                
                self.face_results_table.setRowHidden(row, not show)
    
    def open_photo_from_face_results(self, index):
        """Open photo location when double-clicked in face results"""
        row = index.row()
        photo_id = int(self.face_results_table.item(row, 0).text())
        
        # Switch to Library tab and select the photo
        self.tabs.setCurrentIndex(1)
        
        # Find and select the photo in the main table
        for i in range(self.photo_table.rowCount()):
            if int(self.photo_table.item(i, 0).text()) == photo_id:
                self.photo_table.selectRow(i)
                self.photo_table.scrollToItem(self.photo_table.item(i, 0))
                break
    
    def refresh_learning_data(self):
        """Refresh the AI learning data display"""
        self.learning_table.setSortingEnabled(False)
        self.learning_table.setRowCount(0)
        
        try:
            # Get correction statistics
            corrections = self.db.cursor.execute('''
                SELECT 
                    field_name,
                    original_value,
                    corrected_value,
                    COUNT(*) as count,
                    MAX(correction_date) as last_date
                FROM ai_corrections
                WHERE original_value IS NOT NULL 
                AND corrected_value IS NOT NULL
                AND original_value != corrected_value
                GROUP BY field_name, original_value, corrected_value
                ORDER BY count DESC, last_date DESC
            ''').fetchall()
            
            for field, orig, corrected, count, last_date in corrections:
                row = self.learning_table.rowCount()
                self.learning_table.insertRow(row)
                
                # Field name (readable)
                field_readable = field.replace('_', ' ').title()
                self.learning_table.setItem(row, 0, QTableWidgetItem(field_readable))
                
                # Original value
                self.learning_table.setItem(row, 1, QTableWidgetItem(orig or 'unknown'))
                
                # Corrected value
                self.learning_table.setItem(row, 2, QTableWidgetItem(corrected or ''))
                
                # Count
                self.learning_table.setItem(row, 3, QTableWidgetItem(str(count)))
                
                # Last correction date
                self.learning_table.setItem(row, 4, QTableWidgetItem(last_date or ''))
            
            self.statusBar().showMessage(f"Loaded {len(corrections)} learned patterns", 2000)
        except Exception as e:
            print(f"Error loading learning data: {e}")
        
        self.learning_table.setSortingEnabled(True)
    
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
                self.db.cursor.execute('DELETE FROM ai_corrections')
                self.db.conn.commit()
                self.refresh_learning_data()
                self.statusBar().showMessage("Learning data cleared (backup created)", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear learning data: {e}")
    
    def backup_learning_data(self):
        """Backup learning data to a backup table"""
        try:
            from datetime import datetime
            backup_table = f"ai_corrections_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Create backup table
            self.db.cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {backup_table} AS 
                SELECT * FROM ai_corrections
            ''')
            self.db.conn.commit()
            
            # Keep only last 5 backups
            self.cleanup_old_backups()
            
            print(f"Created backup: {backup_table}")
            return True
        except Exception as e:
            print(f"Failed to create backup: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Keep only the 5 most recent backups"""
        try:
            # Get all backup tables
            self.db.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'ai_corrections_backup_%'"
            )
            backups = [row[0] for row in self.db.cursor.fetchall()]
            
            # Sort by date (newest first) and keep only 5
            backups.sort(reverse=True)
            for old_backup in backups[5:]:
                self.db.cursor.execute(f'DROP TABLE IF EXISTS {old_backup}')
                print(f"Cleaned up old backup: {old_backup}")
            
            self.db.conn.commit()
        except Exception as e:
            print(f"Error cleaning up backups: {e}")
    
    def manual_backup_learning_data(self):
        """Manual backup triggered by user"""
        if self.backup_learning_data():
            QMessageBox.information(
                self,
                "Backup Created",
                "AI learning data has been backed up successfully!\n\n"
                "The system keeps the 5 most recent backups."
            )
        else:
            QMessageBox.critical(
                self,
                "Backup Failed",
                "Failed to create backup. Check console for errors."
            )
    
    def restore_learning_data(self):
        """Restore learning data from backup"""
        try:
            # Get available backups
            self.db.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'ai_corrections_backup_%' ORDER BY name DESC"
            )
            backups = [row[0] for row in self.db.cursor.fetchall()]
            
            if not backups:
                QMessageBox.information(
                    self,
                    "No Backups",
                    "No backup files found."
                )
                return
            
            # Let user choose which backup
            from PyQt6.QtWidgets import QInputDialog
            
            # Format backup names for display
            backup_labels = []
            for b in backups:
                # Extract datetime from name: ai_corrections_backup_20250101_120000
                parts = b.split('_')
                if len(parts) >= 4:
                    date_str = parts[3]
                    time_str = parts[4] if len(parts) > 4 else "000000"
                    formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
                    backup_labels.append(formatted)
                else:
                    backup_labels.append(b)
            
            item, ok = QInputDialog.getItem(
                self,
                "Restore Backup",
                "Select backup to restore:",
                backup_labels,
                0,
                False
            )
            
            if ok and item:
                # Get the actual table name
                selected_backup = backups[backup_labels.index(item)]
                
                # Confirm restore
                reply = QMessageBox.question(
                    self,
                    "Confirm Restore",
                    f"Restore learning data from backup:\n{item}?\n\n"
                    "This will replace current learning data.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    # Clear current data and restore from backup
                    self.db.cursor.execute('DELETE FROM ai_corrections')
                    self.db.cursor.execute(f'''
                        INSERT INTO ai_corrections 
                        SELECT * FROM {selected_backup}
                    ''')
                    self.db.conn.commit()
                    
                    self.refresh_learning_data()
                    self.statusBar().showMessage(f"Restored from backup: {item}", 3000)
                    QMessageBox.information(
                        self,
                        "Restore Complete",
                        f"Learning data restored from backup:\n{item}"
                    )
        except Exception as e:
            QMessageBox.critical(self, "Restore Failed", f"Failed to restore backup: {e}")
            import traceback
            traceback.print_exc()
    
    def load_vocabulary_for_field(self, field_name):
        """Load vocabulary values for selected field"""
        self.vocab_list.blockSignals(True)
        self.vocab_list.setRowCount(0)
        
        vocab_with_desc = self.db.get_vocabulary(field_name, include_descriptions=True)
        
        for value, description in vocab_with_desc:
            # Count usage
            self.db.cursor.execute(
                f'SELECT COUNT(*) FROM photos WHERE {field_name} = ?',
                (value,)
            )
            count = self.db.cursor.fetchone()[0]
            
            row = self.vocab_list.rowCount()
            self.vocab_list.insertRow(row)
            
            value_item = QTableWidgetItem(value)
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.vocab_list.setItem(row, 0, value_item)
            
            desc_item = QTableWidgetItem(description or '')
            self.vocab_list.setItem(row, 1, desc_item)
            
            count_item = QTableWidgetItem(str(count))
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.vocab_list.setItem(row, 2, count_item)
        
        self.vocab_list.blockSignals(False)
    
    def on_vocab_description_changed(self, item):
        """Handle when description is edited"""
        if item.column() != 1:  # Only description column
            return
        
        row = item.row()
        value = self.vocab_list.item(row, 0).text()
        description = item.text()
        field = self.vocab_field_selector.currentText()
        
        self.db.update_vocabulary_description(field, value, description)
        self.statusBar().showMessage(f"Updated description for '{value}'", 2000)
    
    def add_vocabulary_value(self):
        """Add new vocabulary value"""
        value = self.vocab_input.text().strip().lower()
        if not value:
            return
        
        field = self.vocab_field_selector.currentText()
        if self.db.add_vocabulary_value(field, value):
            self.load_vocabulary_for_field(field)
            self.vocab_input.clear()
            self.statusBar().showMessage(f"Added '{value}' to {field}", 2000)
        else:
            QMessageBox.warning(self, "Error", f"Value '{value}' already exists or invalid")
    
    def rename_vocabulary_value(self):
        """Rename selected vocabulary value"""
        selected = self.vocab_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select a value to rename")
            return
        
        old_value = self.vocab_list.item(selected[0].row(), 0).text()
        field = self.vocab_field_selector.currentText()
        
        new_value, ok = QInputDialog.getText(
            self, "Rename Value",
            f"Rename '{old_value}' to:",
            text=old_value
        )
        
        if ok and new_value.strip():
            if self.db.rename_vocabulary_value(field, old_value, new_value.strip().lower()):
                self.load_vocabulary_for_field(field)
                self.refresh_photos()  # Refresh table to show updated values
                self.statusBar().showMessage(f"Renamed '{old_value}' to '{new_value}'", 2000)
            else:
                QMessageBox.warning(self, "Error", "Failed to rename value")
    
    def delete_vocabulary_value(self):
        """Delete selected vocabulary value"""
        selected = self.vocab_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select a value to delete")
            return
        
        value = self.vocab_list.item(selected[0].row(), 0).text()
        count = int(self.vocab_list.item(selected[0].row(), 1).text())
        
        if count > 0:
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"'{value}' is used by {count} photo(s). Delete anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        field = self.vocab_field_selector.currentText()
        self.db.remove_vocabulary_value(field, value)
        self.load_vocabulary_for_field(field)
        self.statusBar().showMessage(f"Deleted '{value}' from {field}", 2000)
    
    def cleanup_vocabulary(self):
        """Remove unused vocabulary values"""
        field = self.vocab_field_selector.currentText()
        self.db.cleanup_unused_vocabulary(field)
        self.load_vocabulary_for_field(field)
        self.statusBar().showMessage(f"Cleaned unused values from {field}", 2000)
    
    def setup_table_delegates(self):
        """Setup dropdown delegates for table columns using controlled vocabularies"""
        try:
            # Column mapping: column_index -> field_name
            vocab_columns = {
                self.COL_TYPE: 'type_of_shot',
                self.COL_POSE: 'pose',
                self.COL_FACING: 'facing_direction',
                self.COL_LEVEL: 'explicit_level',
                self.COL_COLOR: 'color_of_clothing',
                self.COL_MATERIAL: 'material',
                self.COL_CLOTHING: 'type_clothing',
                self.COL_FOOTWEAR: 'footwear',
                self.COL_LOCATION: 'location'
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
    
    def save_last_folder(self, folder):
        """Save the last used folder to settings"""
        self.settings.setValue("last_folder", folder)
        self.settings.sync()  # Force write to disk
        print(f"Saved folder to settings: {folder}")
    
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
        
        self.analyzer_thread = AnalyzerThread(
            folder, 
            self.subfolder_checkbox.isChecked(),
            "H:\\NovaApp\\nova_photos.db"  # Pass path instead of connection
        )
        self.analyzer_thread.progress.connect(self.update_progress)
        self.analyzer_thread.photo_analyzed.connect(self.add_photo_to_table)
        self.analyzer_thread.finished.connect(self.analysis_finished)
        self.analyzer_thread.error.connect(self.analysis_error)
        self.analyzer_thread.start()
    
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
    
    def analysis_error(self, error_msg):
        """Called when an error occurs"""
        QMessageBox.warning(self, "Error", f"An error occurred: {error_msg}")
        self.status_label.setText(f"Error: {error_msg}")
    
    def add_photo_to_table(self, photo):
        """Add a single photo to the table"""
        row = self.photo_table.rowCount()
        self.photo_table.insertRow(row)
        
        # Block signals and sorting while populating
        self.photo_table.blockSignals(True)
        self.photo_table.setSortingEnabled(False)
        
        # Set row height based on thumbnail size
        thumb_size = self.thumbnail_sizes[self.current_thumb_size]
        if thumb_size > 0:
            self.photo_table.setRowHeight(row, thumb_size + 10)
        
        # Checkbox column (column 0) - use an actual QCheckBox widget for reliability
        chk = QCheckBox()
        chk.setTristate(False)
        chk.setChecked(photo['id'] in self.persistent_selected_ids)
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
        
        # Add thumbnail (now column 2)
        self.add_thumbnail(row, self.COL_THUMBNAIL, photo['filepath'])
        
        self.photo_table.setItem(row, self.COL_TYPE, QTableWidgetItem(photo['type_of_shot'] or ''))
        self.photo_table.setItem(row, self.COL_POSE, QTableWidgetItem(photo['pose'] or ''))
        self.photo_table.setItem(row, self.COL_FACING, QTableWidgetItem(photo['facing_direction'] or ''))
        self.photo_table.setItem(row, self.COL_LEVEL, QTableWidgetItem(photo['explicit_level'] or ''))
        self.photo_table.setItem(row, self.COL_COLOR, QTableWidgetItem(photo['color_of_clothing'] or ''))
        self.photo_table.setItem(row, self.COL_MATERIAL, QTableWidgetItem(photo['material'] or ''))
        self.photo_table.setItem(row, self.COL_CLOTHING, QTableWidgetItem(photo['type_clothing'] or ''))
        self.photo_table.setItem(row, self.COL_FOOTWEAR, QTableWidgetItem(photo['footwear'] or ''))
        location_item = QTableWidgetItem(photo['location'] or '')
        location_item.setToolTip(f"Location: {photo['location'] or 'Not set'}")
        self.photo_table.setItem(row, self.COL_LOCATION, location_item)
        
        # Status text (column 12)
        status_map = {'raw': 'Raw', 'needs_edit': 'Needs Edit', 'ready': 'Ready for Release', 'released': 'Released'}
        self.photo_table.setItem(row, self.COL_STATUS, QTableWidgetItem(status_map.get(photo.get('status', 'raw'), 'Raw')))
        
        # Checkboxes for release status (columns 13-15)
        ig_item = QTableWidgetItem()
        ig_item.setFlags(ig_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        ig_item.setCheckState(Qt.CheckState.Checked if photo['released_instagram'] else Qt.CheckState.Unchecked)
        self.photo_table.setItem(row, self.COL_IG, ig_item)
        
        tiktok_item = QTableWidgetItem()
        tiktok_item.setFlags(tiktok_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        tiktok_item.setCheckState(Qt.CheckState.Checked if photo['released_tiktok'] else Qt.CheckState.Unchecked)
        self.photo_table.setItem(row, self.COL_TIKTOK, tiktok_item)
        
        fansly_item = QTableWidgetItem()
        fansly_item.setFlags(fansly_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        fansly_item.setCheckState(Qt.CheckState.Checked if photo['released_fansly'] else Qt.CheckState.Unchecked)
        self.photo_table.setItem(row, self.COL_FANSLY, fansly_item)
        
        packages = self.db.get_packages(photo['id'])
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
        dlg = LightboxDialog(filepath, photo_id, self.db, self)
        dlg.show()
        if not hasattr(self, '_image_dialogs'):
            self._image_dialogs = []
        self._image_dialogs.append(dlg)

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
        """Apply filters to photo list"""
        all_photos = self.db.get_all_photos()
        
        # Filter by status
        status_filters = []
        if self.filter_raw.isChecked():
            status_filters.append('raw')
        if self.filter_needs_edit.isChecked():
            status_filters.append('needs_edit')
        if self.filter_ready.isChecked():
            status_filters.append('ready')
        if self.filter_released.isChecked():
            status_filters.append('released')
        
        # Unknown values filter
        show_only_unknowns = self.filter_unknowns.isChecked()
        
        # Get metadata filter values
        filter_type = self.filter_type.currentText() if self.filter_type.currentText() != "(Any)" else ""
        filter_pose = self.filter_pose.currentText() if self.filter_pose.currentText() != "(Any)" else ""
        filter_facing = self.filter_facing.currentText() if self.filter_facing.currentText() != "(Any)" else ""
        filter_level = self.filter_level.currentText() if self.filter_level.currentText() != "(Any)" else ""
        filter_color = self.filter_color.text().strip().lower()
        filter_material = self.filter_material.text().strip().lower()
        filter_clothing = self.filter_clothing.text().strip().lower()
        filter_footwear = self.filter_footwear.text().strip().lower()
        filter_location = self.filter_location.text().strip().lower()
        filter_package = self.filter_package.text().strip().lower()
        face_match_filter = self.filter_face_match.currentText() if hasattr(self, 'filter_face_match') else "(Any)"
        
        # Filter photos
        filtered_photos = []
        for photo in all_photos:
            # Unknown values filter
            if show_only_unknowns:
                has_unknown = False
                ai_fields = ['type_of_shot', 'pose', 'facing_direction', 'explicit_level', 
                           'color_of_clothing', 'material', 'type_clothing', 'footwear', 'location']
                for field in ai_fields:
                    if photo.get(field) == 'unknown':
                        has_unknown = True
                        break
                if not has_unknown:
                    continue
            
            # Status filter
            if status_filters and photo.get('status', 'raw') not in status_filters:
                continue
            
            # Platform filters
            if self.filter_ig.isChecked() and not photo['released_instagram']:
                continue
            if self.filter_tiktok.isChecked() and not photo['released_tiktok']:
                continue
            if self.filter_fansly.isChecked() and not photo['released_fansly']:
                continue
            
            # Metadata filters (case-insensitive partial match)
            if filter_type and filter_type.lower() not in (photo.get('type_of_shot') or '').lower():
                continue
            if filter_pose and filter_pose.lower() not in (photo.get('pose') or '').lower():
                continue
            if filter_facing and filter_facing.lower() not in (photo.get('facing_direction') or '').lower():
                continue
            if filter_level and filter_level.lower() not in (photo.get('explicit_level') or '').lower():
                continue
            if filter_color and filter_color not in (photo.get('color_of_clothing') or '').lower():
                continue
            if filter_material and filter_material not in (photo.get('material') or '').lower():
                continue
            if filter_clothing and filter_clothing not in (photo.get('type_clothing') or '').lower():
                continue
            if filter_footwear and filter_footwear not in (photo.get('footwear') or '').lower():
                continue
            if filter_location and filter_location not in (photo.get('location') or '').lower():
                continue
            if filter_package:
                pkgs = self.db.get_packages(photo['id'])
                pkg_match = any(filter_package in p.lower() for p in pkgs)
                legacy_match = filter_package in (photo.get('package_name') or '').lower()
                if not (pkg_match or legacy_match):
                    continue

            # Face match rating filter
            if face_match_filter and face_match_filter != "(Any)":
                rating = int(photo.get('face_similarity') or 0)
                if face_match_filter == "Unrated":
                    if rating != 0:
                        continue
                elif face_match_filter == "5 stars":
                    if rating != 5:
                        continue
                elif face_match_filter == "4-5 stars":
                    if rating < 4:
                        continue
                elif face_match_filter == "3-5 stars":
                    if rating < 3:
                        continue
                elif face_match_filter == "2-5 stars":
                    if rating < 2:
                        continue
                elif face_match_filter == "1-5 stars":
                    if rating < 1:
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
            
            self.photo_table.setItem(i, 2, QTableWidgetItem(photo['type_of_shot'] or ''))
            self.photo_table.setItem(i, 3, QTableWidgetItem(photo['pose'] or ''))
            self.photo_table.setItem(i, 4, QTableWidgetItem(photo['facing_direction'] or ''))
            self.photo_table.setItem(i, 5, QTableWidgetItem(photo['explicit_level'] or ''))
            self.photo_table.setItem(i, 6, QTableWidgetItem(photo['color_of_clothing'] or ''))
            self.photo_table.setItem(i, 7, QTableWidgetItem(photo['material'] or ''))
            self.photo_table.setItem(i, 8, QTableWidgetItem(photo['type_clothing'] or ''))
            self.photo_table.setItem(i, 9, QTableWidgetItem(photo['footwear'] or ''))
            self.photo_table.setItem(i, 10, QTableWidgetItem(photo['location'] or ''))
            
            # Status text
            status_map = {'raw': 'Raw', 'needs_edit': 'Needs Edit', 'ready': 'Ready for Release', 'released': 'Released'}
            self.photo_table.setItem(i, 11, QTableWidgetItem(status_map.get(photo.get('status', 'raw'), 'Raw')))
            
            # Checkboxes for release status
            ig_item = QTableWidgetItem()
            ig_item.setFlags(ig_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            ig_item.setCheckState(Qt.CheckState.Checked if photo['released_instagram'] else Qt.CheckState.Unchecked)
            self.photo_table.setItem(i, 12, ig_item)
            
            tiktok_item = QTableWidgetItem()
            tiktok_item.setFlags(tiktok_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            tiktok_item.setCheckState(Qt.CheckState.Checked if photo['released_tiktok'] else Qt.CheckState.Unchecked)
            self.photo_table.setItem(i, 13, tiktok_item)
            
            fansly_item = QTableWidgetItem()
            fansly_item.setFlags(fansly_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            fansly_item.setCheckState(Qt.CheckState.Checked if photo['released_fansly'] else Qt.CheckState.Unchecked)
            self.photo_table.setItem(i, 14, fansly_item)
            
            packages = self.db.get_packages(photo['id'])
            package_display = ', '.join(packages) if packages else (photo.get('package_name') or '')
            self.photo_table.setItem(i, 15, QTableWidgetItem(package_display))
            
            # Tags column
            self.photo_table.setItem(i, 16, QTableWidgetItem(photo['tags'] or ''))
            
            # Face Match rating (column 17)
            face_match = photo.get('face_similarity', 0)
            if face_match > 0:
                stars = "⭐" * face_match
                self.photo_table.setItem(i, 17, QTableWidgetItem(stars))
            else:
                self.photo_table.setItem(i, 17, QTableWidgetItem(""))
            
            # Date Created - read only (column 18) without fractional seconds
            raw_date = str(photo['date_created'] or '')
            if '.' in raw_date:
                raw_date = raw_date.split('.')[0]
            date_item = QTableWidgetItem(raw_date)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.photo_table.setItem(i, 18, date_item)
            
            filepath_item = QTableWidgetItem(photo['filepath'] or '')
            filepath_item.setToolTip(photo['filepath'] or 'No path')
            self.photo_table.setItem(i, 19, filepath_item)

            # Notes column (20)
            self.photo_table.setItem(i, 20, QTableWidgetItem(photo.get('notes') or ''))
        
        self.photo_table.setSortingEnabled(True)
        self.statusBar().showMessage(f"Filtered: {len(filtered_photos)} of {len(all_photos)} photos", 5000)
        
        # Also refresh gallery with filtered results
        self.refresh_gallery_with_photos(filtered_photos)
    
    def clear_filters(self):
        """Clear all filters and show all photos"""
        # Status filters
        self.filter_raw.setChecked(False)
        self.filter_needs_edit.setChecked(False)
        self.filter_ready.setChecked(False)
        self.filter_released.setChecked(False)
        
        # Platform filters
        self.filter_ig.setChecked(False)
        self.filter_tiktok.setChecked(False)
        self.filter_fansly.setChecked(False)
        
        # Metadata filters
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
        if hasattr(self, 'filter_face_match'):
            self.filter_face_match.setCurrentIndex(0)
        
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
        non_editable = [self.COL_CHECKBOX, self.COL_ID, self.COL_THUMBNAIL, self.COL_IG, self.COL_TIKTOK, self.COL_FANSLY, self.COL_DATE]
        editable_items = [item for item in selected_items if item.column() not in non_editable]
        
        if not editable_items:
            QMessageBox.information(self, "No Editable Cells", "Please select editable metadata cells (not ID, Thumbnail, Date, or checkboxes)")
            return
        
        # Get the column name for display
        column_names = {
            self.COL_TYPE: 'Type',
            self.COL_POSE: 'Pose',
            self.COL_FACING: 'Facing',
            self.COL_LEVEL: 'Level',
            self.COL_COLOR: 'Color',
            self.COL_MATERIAL: 'Material',
            self.COL_CLOTHING: 'Clothing',
            self.COL_FOOTWEAR: 'Footwear',
            self.COL_LOCATION: 'Location',
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
            ai_fields = ['type_of_shot', 'pose', 'facing_direction', 'explicit_level', 
                        'color_of_clothing', 'material', 'type_clothing', 'footwear', 'location']
            
            updates = []
            tags_updated = False
            for item in editable_items:
                col = item.column()
                row = item.row()
                photo_id = self.get_photo_id_from_row(row)
                if photo_id is None:
                    continue

                if col == self.COL_STATUS:  # Status - special handling
                    status_map = {'Raw': 'raw', 'Needs Edit': 'needs_edit', 'Ready for Release': 'ready', 'Released': 'released'}
                    db_value = status_map.get(text, text.lower().replace(' ', '_'))
                    self.db.update_photo_metadata(photo_id, {'status': db_value})
                    reverse_map = {v: k for k, v in status_map.items()}
                    item.setText(reverse_map.get(db_value, text))
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
                            print(f"Saving correction for photo {photo_id}, {field_name}: '{original_value}' -> '{text}'")
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
        status_map = {'Raw': 'raw', 'Needs Edit': 'needs_edit', 'Ready for Release': 'ready', 'Released': 'released'}
        status_value = status_map[status_text]
        
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
            'released_fansly': self.COL_FANSLY
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
        print("=== REANALYZE SELECTED CALLED ===")
        target_ids = list(self.get_target_photo_ids())
        print(f"Target IDs: {target_ids}")
        if not target_ids:
            QMessageBox.information(self, "No Selection", "Please check photos to re-analyze (or select cells)")
            return
        photos_to_analyze = []
        for photo_id in target_ids:
            print(f"Getting photo ID: {photo_id}")
            photo = self.db.get_photo(photo_id)
            print(f"Photo data: {photo}")
            if photo and photo.get('filepath'):
                photos_to_analyze.append(photo)
            else:
                print(f"WARNING: Photo {photo_id} has no filepath!")
        
        print(f"Total photos to analyze: {len(photos_to_analyze)}")
        
        if not photos_to_analyze:
            print("No photos to analyze, returning")
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
        elif hasattr(self, 'reanalyzer_thread') and self.reanalyzer_thread and self.reanalyzer_thread.isRunning():
            self.reanalyzer_thread.stop()
            self.statusBar().showMessage('Cancelling re-analysis...', 3000)
            self.cancel_btn.setEnabled(False)
            self.analyze_btn.setEnabled(True)
    
    def refresh_tag_cloud(self):
        """Refresh the tag cloud display"""
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
            # Wait for thread with timeout to prevent freeze
            if not self.analyzer_thread.wait(2000):  # 2 second timeout
                self.analyzer_thread.terminate()
        self.db.close()
        event.accept()


def main():
    try:
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
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")


if __name__ == '__main__':
    main()

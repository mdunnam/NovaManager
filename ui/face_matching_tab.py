"""
Face Matching tab extracted from the monolithic main window.
"""
import os
from pathlib import Path
from face_matcher_v2 import FaceMatcherV2
from face_matcher_deepface import FaceMatcherDeepFace
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QScrollArea,
    QGridLayout,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QFileDialog,
    QHeaderView,
    QAbstractItemView,
    QFrame,
    QToolButton,
    QStyle,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QIcon


class FaceMatchingTab(QWidget):
    """Encapsulates face matching benchmarks and analysis results."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.benchmark_photos = []
        self.face_matcher = None
        self.matcher_type = "opencv"  # Default to OpenCV
        self._build_ui()
        self.load_benchmarks_from_settings()
        self.render_benchmark_grid()
        self.load_face_similarity_results()
        self._initialize_matcher()

    # UI builders
    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Upload 5-10 reference photos of the target face. "
            "The system will rate all photos in your library 1-5 based on face similarity."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Face matcher selection
        matcher_layout = QHBoxLayout()
        matcher_layout.addWidget(QLabel("<b>Face Matcher:</b>"))
        
        self.matcher_combo = QComboBox()
        self.matcher_combo.addItem("OpenCV (Fast, Lightweight)", "opencv")
        self.matcher_combo.addItem("DeepFace (Most Accurate)", "deepface")
        self.matcher_combo.currentIndexChanged.connect(self._on_matcher_changed)
        self.matcher_combo.setToolTip(
            "OpenCV: Fast, lightweight, good for most use cases\n"
            "DeepFace: Most accurate, requires TensorFlow (first run downloads ~100MB model)"
        )
        matcher_layout.addWidget(self.matcher_combo)
        matcher_layout.addStretch()
        layout.addLayout(matcher_layout)

        content_layout = QHBoxLayout()

        # LEFT: Benchmark photos
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        benchmark_label = QLabel("<b>Reference Photos</b>")
        left_layout.addWidget(benchmark_label)

        self.benchmark_scroll = QScrollArea()
        self.benchmark_scroll.setWidgetResizable(True)
        self.benchmark_container = QWidget()
        self.benchmark_grid = QGridLayout(self.benchmark_container)
        self.benchmark_grid.setContentsMargins(4, 4, 4, 4)
        self.benchmark_grid.setSpacing(8)
        self.benchmark_scroll.setWidget(self.benchmark_container)
        left_layout.addWidget(self.benchmark_scroll, 1)

        benchmark_buttons = QHBoxLayout()
        add_benchmark_btn = QPushButton("Add Photos")
        add_benchmark_btn.clicked.connect(self.add_benchmark_photos)
        benchmark_buttons.addWidget(add_benchmark_btn)

        clear_benchmark_btn = QPushButton("Clear All")
        clear_benchmark_btn.clicked.connect(self.clear_benchmark_photos)
        benchmark_buttons.addWidget(clear_benchmark_btn)
        left_layout.addLayout(benchmark_buttons)

        run_btn = QPushButton("🔍 Analyze All Photos")
        run_btn.clicked.connect(self.run_analysis)
        run_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        left_layout.addWidget(run_btn)
        content_layout.addWidget(left_widget, 1)

        # RIGHT: Log output
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

        # Results section
        results_label = QLabel("<b>Results:</b> (Filter photos by similarity rating)")
        layout.addWidget(results_label)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Show photos rated:"))

        self.rating_filter = QComboBox()
        self.rating_filter.addItems(["All", "5 stars", "4-5 stars", "3-5 stars", "2-5 stars", "1-5 stars", "Unrated"])
        self.rating_filter.currentTextChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.rating_filter)

        flag_btn = QPushButton("🚩 Flag Selected with Rating")
        flag_btn.clicked.connect(self.flag_selected_photos)
        filter_layout.addWidget(flag_btn)

        clear_results_btn = QPushButton("Clear Results")
        clear_results_btn.setToolTip("Reset face match ratings to unrated (0) and clear benchmark photos")
        clear_results_btn.clicked.connect(self.clear_results)
        filter_layout.addWidget(clear_results_btn)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        self.face_results_table = QTableWidget()
        self.face_results_table.setColumnCount(6)
        self.face_results_table.setHorizontalHeaderLabels(
            ["ID", "Thumbnail", "Filename", "Rating", "Confidence", "Flag"]
        )

        self.face_results_table.setColumnWidth(0, 40)
        self.face_results_table.setColumnWidth(1, 60)
        self.face_results_table.setColumnWidth(2, 250)
        self.face_results_table.setColumnWidth(3, 80)
        self.face_results_table.setColumnWidth(4, 100)
        self.face_results_table.setColumnWidth(5, 50)

        self.face_results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.face_results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.face_results_table.setAlternatingRowColors(True)
        self.face_results_table.setSortingEnabled(True)
        self.face_results_table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.face_results_table.doubleClicked.connect(self.open_photo_from_results)
        layout.addWidget(self.face_results_table)

    # API methods
    def add_benchmark_photos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Benchmark Reference Photos",
            "",
            "Images (*.jpg *.jpeg *.png)",
        )

        if files:
            added = 0
            for file in files:
                if file not in self.benchmark_photos:
                    self.benchmark_photos.append(file)
                    added += 1
            self.save_benchmarks_to_settings()
            self.render_benchmark_grid()
            if self.controller.statusBar():
                self.controller.statusBar().showMessage(
                    f"Added {added} benchmark photo(s). Total: {len(self.benchmark_photos)}", 3000
                )

    def clear_benchmark_photos(self):
        self.benchmark_photos.clear()
        self.save_benchmarks_to_settings()
        while self.benchmark_grid.count():
            item = self.benchmark_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        if self.controller.statusBar():
            self.controller.statusBar().showMessage("Cleared all benchmark photos", 2000)

    def save_benchmarks_to_settings(self):
        try:
            self.controller.settings.setValue("face_benchmarks", ";".join(self.benchmark_photos))
        except Exception as exc:
            print(f"Settings save error: {exc}")

    def load_benchmarks_from_settings(self):
        try:
            saved = self.controller.settings.value("face_benchmarks", "")
            if saved:
                paths = [p for p in str(saved).split(";") if p]
                self.benchmark_photos = paths
        except Exception as exc:
            print(f"Settings load error: {exc}")

    def render_benchmark_grid(self):
        while self.benchmark_grid.count():
            item = self.benchmark_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        if not self.benchmark_photos:
            return

        cols = 5
        for idx, path in enumerate(self.benchmark_photos):
            r, c = divmod(idx, cols)
            frame = QFrame()
            frame.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
            v = QVBoxLayout(frame)
            v.setContentsMargins(2, 2, 2, 2)
            v.setSpacing(2)

            img = QLabel()
            img.setFixedSize(100, 100)
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if os.path.exists(path):
                pm = QPixmap(path)
                if not pm.isNull():
                    img.setPixmap(
                        pm.scaled(
                            100,
                            100,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    img.setText("[No Preview]")
                    img.setStyleSheet("QLabel { font-size: 9px; color: gray; }")
            else:
                img.setText("[Missing]")
                img.setStyleSheet("QLabel { font-size: 9px; color: red; }")
            img.setToolTip(Path(path).name)
            v.addWidget(img)

            del_btn = QToolButton()
            del_btn.setToolTip("Remove from benchmarks")
            del_btn.setMaximumSize(20, 20)
            try:
                del_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
            except Exception:
                del_btn.setText("X")
            del_btn.clicked.connect(lambda _=False, p=path: self.delete_benchmark_path(p))
            v.addWidget(del_btn)

            self.benchmark_grid.addWidget(frame, r, c)

    def delete_benchmark_path(self, path):
        try:
            self.benchmark_photos = [p for p in self.benchmark_photos if p != path]
            self.save_benchmarks_to_settings()
            self.render_benchmark_grid()
            if self.controller.statusBar():
                self.controller.statusBar().showMessage("Removed benchmark photo", 2000)
        except Exception as exc:
            print(f"Delete benchmark error: {exc}")

    def run_analysis(self):
        """Run face matching analysis on all photos in library."""
        self.face_log_output.clear()
        self.face_log_output.append("[INFO] Face matching analysis started...")
        
        if not self.benchmark_photos:
            self.face_log_output.append("[ERROR] No benchmark photos loaded. Please add reference photos first.")
            QMessageBox.warning(self, "No Benchmarks", "Please add reference photos before running analysis.")
            return
        
        try:
            # Initialize matcher if needed
            if self.face_matcher is None:
                self._initialize_matcher()
            
            # Clear and reload benchmarks
            self.face_log_output.append(f"[INFO] Loading {len(self.benchmark_photos)} benchmark(s)...")
            self.face_matcher.clear_benchmarks()
            
            for idx, benchmark_path in enumerate(self.benchmark_photos, 1):
                if os.path.exists(benchmark_path):
                    success = self.face_matcher.add_benchmark(benchmark_path, name=f"Benchmark_{idx}")
                    if success:
                        self.face_log_output.append(f"[OK] Loaded benchmark {idx}/{len(self.benchmark_photos)}")
                    else:
                        self.face_log_output.append(f"[WARN] No face detected in benchmark {idx}")
                else:
                    self.face_log_output.append(f"[ERROR] Benchmark file not found: {benchmark_path}")
            
            # Get all photos from database
            self.face_log_output.append("[INFO] Fetching photos from database...")
            photos = self.controller.db.get_all_photos()
            self.face_log_output.append(f"[INFO] Found {len(photos)} photos to analyze")
            
            # Analyze each photo
            analyzed = 0
            rated = 0
            for idx, photo in enumerate(photos, 1):
                photo_id = photo['id']
                filepath = photo['filepath']
                
                if not os.path.exists(filepath):
                    continue
                
                # Compare face
                details = self.face_matcher.compare_face(filepath, return_details=True)
                
                if 'error' not in details:
                    rating = details['rating']
                    similarity = details.get('best_similarity', 0)
                    
                    # Update database with rating
                    self.controller.db.update_photo(photo_id, face_match_rating=rating)
                    
                    if rating > 0:
                        rated += 1
                        self.face_log_output.append(
                            f"[{idx}/{len(photos)}] {Path(filepath).name}: {rating} stars (sim: {similarity:.3f})"
                        )
                
                analyzed += 1
                
                # Update progress every 10 photos
                if analyzed % 10 == 0:
                    self.face_log_output.append(f"[PROGRESS] Analyzed {analyzed}/{len(photos)} photos...")
                    self.face_log_output.repaint()
            
            self.face_log_output.append(f"\n[COMPLETE] Analysis finished!")
            self.face_log_output.append(f"[STATS] Analyzed: {analyzed}, Rated: {rated}")
            
            # Reload results
            self.load_face_similarity_results()
            
            QMessageBox.information(
                self, 
                "Analysis Complete", 
                f"Analyzed {analyzed} photos.\n{rated} photos received ratings."
            )
            
        except Exception as e:
            self.face_log_output.append(f"[ERROR] Analysis failed: {str(e)}")
            QMessageBox.critical(self, "Error", f"Analysis failed: {str(e)}")

    def apply_filter(self):
        """Apply rating filter to results table."""
        # Placeholder: filter logic to be implemented
        pass

    def flag_selected_photos(self):
        """Flag selected photos with rating."""
        rows = self.face_results_table.selectedIndexes()
        if not rows:
            QMessageBox.information(self, "No Selection", "Please select photos in the results table")
            return

    def load_face_similarity_results(self):
        """Load persisted analysis results from database."""
        try:
            # Get all photos with face match ratings
            photos = self.controller.db.get_all_photos()
            
            # Filter to only show rated photos
            rated_photos = [p for p in photos if p.get('face_match_rating', 0) > 0]
            
            self.face_results_table.setRowCount(0)
            self.face_results_table.setSortingEnabled(False)
            
            for photo in rated_photos:
                row = self.face_results_table.rowCount()
                self.face_results_table.insertRow(row)
                
                # ID
                id_item = QTableWidgetItem(str(photo['id']))
                id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.face_results_table.setItem(row, 0, id_item)
                
                # Thumbnail
                thumb_label = QLabel()
                thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if os.path.exists(photo['filepath']):
                    pixmap = QPixmap(photo['filepath'])
                    if not pixmap.isNull():
                        thumb_label.setPixmap(
                            pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        )
                self.face_results_table.setCellWidget(row, 1, thumb_label)
                
                # Filename
                filename_item = QTableWidgetItem(Path(photo['filepath']).name)
                self.face_results_table.setItem(row, 2, filename_item)
                
                # Rating
                rating = photo.get('face_match_rating', 0)
                rating_item = QTableWidgetItem("⭐" * rating)
                rating_item.setData(Qt.ItemDataRole.UserRole, rating)
                rating_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.face_results_table.setItem(row, 3, rating_item)
                
                # Confidence (placeholder)
                confidence_item = QTableWidgetItem("-")
                confidence_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.face_results_table.setItem(row, 4, confidence_item)
                
                # Flag
                flag = "✓" if photo.get('flagged', False) else ""
                flag_item = QTableWidgetItem(flag)
                flag_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.face_results_table.setItem(row, 5, flag_item)
            
            self.face_results_table.setSortingEnabled(True)
            self.face_results_table.sortItems(3, Qt.SortOrder.DescendingOrder)  # Sort by rating
            
        except Exception as e:
            print(f"Error loading face similarity results: {e}")

    def open_photo_from_results(self):
        """Open photo from results table in lightbox."""
        pass

    def clear_results(self):
        """Clear all results and benchmarks."""
        reply = QMessageBox.question(
            self,
            "Clear Face Match Results",
            "Reset face match ratings to unrated (0) for all photos and clear benchmark photos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.benchmark_photos.clear()
            self.save_benchmarks_to_settings()
            self.render_benchmark_grid()
            self.face_results_table.setRowCount(0)
            
            # Reset all face match ratings in database
            try:
                photos = self.controller.db.get_all_photos()
                for photo in photos:
                    self.controller.db.update_photo(photo['id'], face_match_rating=0)
                if self.controller.statusBar():
                    self.controller.statusBar().showMessage("Cleared all face match results", 3000)
            except Exception as e:
                print(f"Error clearing results: {e}")
    
    def _initialize_matcher(self):
        """Initialize the selected face matcher."""
        try:
            self.matcher_type = self.matcher_combo.currentData()
            
            if self.matcher_type == "deepface":
                self.face_log_output.append("[INFO] Initializing DeepFace matcher (Facenet model)...")
                self.face_matcher = FaceMatcherDeepFace(
                    model_name="Facenet",
                    detector_backend="opencv"
                )
                self.face_log_output.append("[OK] DeepFace matcher initialized")
            else:
                self.face_log_output.append("[INFO] Initializing OpenCV matcher...")
                self.face_matcher = FaceMatcherV2(confidence_threshold=0.5)
                self.face_log_output.append("[OK] OpenCV matcher initialized")
                
        except Exception as e:
            self.face_log_output.append(f"[ERROR] Failed to initialize matcher: {str(e)}")
            QMessageBox.critical(self, "Initialization Error", f"Failed to initialize face matcher:\n{str(e)}")
    
    def _on_matcher_changed(self):
        """Handle face matcher selection change."""
        self._initialize_matcher()
        if self.controller.statusBar():
            matcher_name = self.matcher_combo.currentText()
            self.controller.statusBar().showMessage(f"Switched to {matcher_name}", 3000)

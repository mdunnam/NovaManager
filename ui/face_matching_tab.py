"""
Face Matching tab extracted from the monolithic main window.
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
        self._build_ui()
        self.load_benchmarks_from_settings()
        self.render_benchmark_grid()
        self.load_face_similarity_results()

    # UI builders
    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Upload 5-10 reference photos of the target face. "
            "The system will rate all photos in your library 1-5 based on face similarity."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

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
        """Stub for AI face matching analysis (to be implemented)."""
        self.face_log_output.clear()
        self.face_log_output.append("[INFO] Face matching analysis started...")
        if not self.benchmark_photos:
            self.face_log_output.append("[ERROR] No benchmark photos loaded. Please add reference photos first.")
            return
        self.face_log_output.append(f"[INFO] Loaded {len(self.benchmark_photos)} benchmark(s)")
        self.face_log_output.append("[INFO] Analysis complete.")

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
        """Load persisted analysis results (placeholder)."""
        pass

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

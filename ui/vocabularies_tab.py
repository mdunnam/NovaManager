"""
Vocabularies tab extracted from the monolithic main window.
"""
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QInputDialog,
    QHeaderView,
    QAbstractItemView,
    QMessageBox,
)


class VocabulariesTab(QWidget):
    """Encapsulates controlled vocabulary management."""

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Title and info
        title = QLabel("<h2>Controlled Vocabularies</h2>")
        layout.addWidget(title)

        info = QLabel(
            "Manage allowed values for each field. AI will only use these values - unknowns will be flagged."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Field selector
        field_layout = QHBoxLayout()
        field_layout.addWidget(QLabel("Field:"))
        self.vocab_field_selector = QComboBox()
        self.vocab_field_selector.addItems([
            "type_of_shot",
            "pose",
            "facing_direction",
            "explicit_level",
            "color_of_clothing",
            "material",
            "type_clothing",
            "footwear",
            "interior_exterior",
            "location",
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

    def load_vocabulary_for_field(self, field_name):
        """Load vocabulary values for selected field."""
        self.vocab_list.setRowCount(0)
        QMessageBox.information(
            self, "Not Implemented", "Vocabulary loading not yet implemented in extracted component"
        )

    def add_vocabulary_value(self):
        """Add new vocabulary value."""
        value = self.vocab_input.text().strip()
        if not value:
            QMessageBox.warning(self, "Empty Value", "Please enter a value")
            return
        QMessageBox.information(self, "Added", f"Added vocabulary value: {value}")
        self.vocab_input.clear()

    def rename_vocabulary_value(self):
        """Rename selected vocabulary value."""
        QMessageBox.information(self, "Not Implemented", "Rename not yet implemented")

    def delete_vocabulary_value(self):
        """Delete selected vocabulary value."""
        QMessageBox.information(self, "Not Implemented", "Delete not yet implemented")

    def cleanup_vocabulary(self):
        """Remove unused vocabulary values."""
        QMessageBox.information(self, "Not Implemented", "Cleanup not yet implemented")

    def on_vocab_description_changed(self, item):
        """Handle description changes."""
        pass

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
from PyQt6.QtCore import Qt


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
        self.vocab_list.blockSignals(True)
        self.vocab_list.setRowCount(0)
        
        vocab_with_desc = self.controller.db.get_vocabulary(field_name, include_descriptions=True)
        
        for value, description in vocab_with_desc:
            # Count usage
            self.controller.db.cursor.execute(
                f'SELECT COUNT(*) FROM photos WHERE {field_name} = ?',
                (value,)
            )
            count = self.controller.db.cursor.fetchone()[0]
            
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

    def add_vocabulary_value(self):
        """Add new vocabulary value."""
        value = self.vocab_input.text().strip().lower()
        if not value:
            return
        
        field = self.vocab_field_selector.currentText()
        if self.controller.db.add_vocabulary_value(field, value):
            self.load_vocabulary_for_field(field)
            self.vocab_input.clear()
            if self.controller.statusBar():
                self.controller.statusBar().showMessage(f"Added '{value}' to {field}", 2000)
        else:
            QMessageBox.warning(self, "Error", f"Value '{value}' already exists or invalid")

    def rename_vocabulary_value(self):
        """Rename selected vocabulary value."""
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
            if self.controller.db.rename_vocabulary_value(field, old_value, new_value.strip().lower()):
                self.load_vocabulary_for_field(field)
                self.controller.refresh_photos()  # Refresh table to show updated values
                if self.controller.statusBar():
                    self.controller.statusBar().showMessage(f"Renamed '{old_value}' to '{new_value}'", 2000)
            else:
                QMessageBox.warning(self, "Error", "Failed to rename value")

    def delete_vocabulary_value(self):
        """Delete selected vocabulary value."""
        selected = self.vocab_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select a value to delete")
            return
        
        value = self.vocab_list.item(selected[0].row(), 0).text()
        count_item = self.vocab_list.item(selected[0].row(), 2)
        count = int(count_item.text()) if count_item else 0
        
        if count > 0:
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"'{value}' is used by {count} photo(s). Delete anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        field = self.vocab_field_selector.currentText()
        self.controller.db.remove_vocabulary_value(field, value)
        self.load_vocabulary_for_field(field)
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(f"Deleted '{value}' from {field}", 2000)

    def cleanup_vocabulary(self):
        """Remove unused vocabulary values."""
        field = self.vocab_field_selector.currentText()
        self.controller.db.cleanup_unused_vocabulary(field)
        self.load_vocabulary_for_field(field)
        if self.controller.statusBar():
            self.controller.statusBar().showMessage(f"Cleaned unused values from {field}", 2000)

    def on_vocab_description_changed(self, item):
        """Handle description changes."""
        if item.column() != 1:  # Only description column
            return
        
        row = item.row()
        value = self.vocab_list.item(row, 0).text()
        description = item.text()
        
        field = self.vocab_field_selector.currentText()
        self.controller.db.set_vocabulary_description(field, value, description)

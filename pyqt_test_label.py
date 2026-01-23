from PyQt6.QtWidgets import QApplication, QLabel

app = QApplication([])
label = QLabel('PyQt Test: If you see this text, PyQt is working!')
label.setMinimumSize(400, 200)
label.show()
app.exec()

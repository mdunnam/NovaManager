# Nova Photo Manager — AI Agent Coding Guide

## Big Picture Architecture
- **Main App:** `nova_manager.py` (PyQt6 GUI) orchestrates all workflows.
- **Database:** `database.py` manages metadata in a SQLite DB (`nova_photos.db`).
- **AI Analysis:** `ai_analyzer.py` uses Ollama (LLaVA model) for image analysis and normalization of attributes.
- **Face Matching:** `face_matcher.py` (OpenCV) and `face_matcher_deepface.py` (DeepFace) provide alternative face recognition methods.
- **Batch/Compare:** `compare_solutions.py`, `publish_tab_method.py` support batch operations and publishing workflows.
- **Tests:** All test scripts are named `test_*.py` and cover GUI, AI, and DB logic.

## Developer Workflows
- **Install dependencies:**
  - `pip install -r requirements.txt`
  - Install Ollama and pull LLaVA: `ollama pull llava`
- **Run app:** `python nova_manager.py`
- **Database location:** All metadata is stored in `nova_photos.db` in the project root.
- **Testing:** Run individual test files (e.g., `python test_face_matcher_v2.py`). No unified test runner.

## Project-Specific Conventions
- **Photo attributes:** Tracked fields include shot type, pose, facing direction, explicit level, clothing, location, workflow status, package name, and dates.
- **AI normalization:** Use mapping dictionaries in `ai_analyzer.py` to standardize attribute values (e.g., facing direction, explicit level).
- **Face matching:**
  - OpenCV-based (`face_matcher.py`) is default for Windows.
  - DeepFace (`face_matcher_deepface.py`) is available for more accurate recognition (requires TensorFlow, not recommended on Windows).
- **Encryption:** API credentials are encrypted using a machine-specific key in `database.py`.
- **Batch operations:** Supported via GUI and scripts; see `publish_tab_method.py` and batch update features in the main app.

## Integration Points
- **Ollama:** Required for AI analysis. Ensure the LLaVA model is pulled and running.
- **OpenCV/DeepFace:** Both are used for face recognition; select based on platform and accuracy needs.
- **PyQt6:** All UI logic is built with PyQt6 widgets and layouts.

## Patterns & Examples
- **Add new photo attribute:** Update DB schema in `database.py`, normalization in `ai_analyzer.py`, and UI in `nova_manager.py`.
- **Face matching:** Use `FaceMatcher` class in `face_matcher.py` for OpenCV, or DeepFace functions in `face_matcher_deepface.py`.
- **Batch update:** Use the GUI's batch update feature or extend `publish_tab_method.py` for custom logic.

## Key Files
- Main app: [nova_manager.py](nova_manager.py)
- Database: [database.py](database.py)
- AI analysis: [ai_analyzer.py](ai_analyzer.py)
- Face matching: [face_matcher.py](face_matcher.py), [face_matcher_deepface.py](face_matcher_deepface.py)
- Requirements: [requirements.txt](requirements.txt)
- Tests: [test_face_matcher_v2.py](test_face_matcher_v2.py), [test_window.py](test_window.py)

---
**Feedback:** If any section is unclear or missing, please specify which workflows, conventions, or integration details need more coverage.

# Nova Photo Manager — AI Agent Coding Guide

## Big Picture Architecture
- **Main App:** `nova_manager.py` (PyQt6 GUI) orchestrates all workflows.
- **Core Modules:** Located in `core/` folder:
  - `database.py` - SQLite database management (stores data in `data/nova_photos.db`)
  - `ai_analyzer.py` - Ollama (LLaVA model) for image analysis
  - `face_matcher_v2.py` - OpenCV-based face matching (fast, lightweight)
  - `face_matcher_deepface.py` - DeepFace face matching (most accurate)
- **UI Components:** `ui/` folder contains PyQt6 tab widgets
- **Scripts:** `scripts/` folder contains utility scripts and batch operations
- **Tests:** `tests/` folder contains all test files (`test_*.py`)
- **Documentation:** `docs/` folder contains guides and quickstart

## Developer Workflows
- **Install dependencies:**
  - `pip install -r requirements.txt`
  - Install Ollama and pull LLaVA: `ollama pull llava`
- **Run app:** `python nova_manager.py`
- **Database location:** All metadata is stored in `data/nova_photos.db` (auto-created on first run).
- **Testing:** Run individual test files from root (e.g., `python tests/test_face_matcher_v2.py`)

## Project-Specific Conventions
- **Photo attributes:** Tracked fields include shot type, pose, facing direction, explicit level, clothing, location, workflow status, package name, and dates.
- **AI normalization:** Use mapping dictionaries in `core/ai_analyzer.py` to standardize attribute values (e.g., facing direction, explicit level).
- **Face matching:**
  - OpenCV-based (`core/face_matcher_v2.py`) is default - fast and lightweight
  - DeepFace (`core/face_matcher_deepface.py`) is available for higher accuracy (requires TensorFlow)
  - Both selectable via UI dropdown
- **Encryption:** API credentials are encrypted using a machine-specific key in `core/database.py`.
- **Batch operations:** Supported via GUI and scripts; see `scripts/` folder

## Integration Points
- **Ollama:** Required for AI analysis. Ensure the LLaVA model is pulled and running.
- **OpenCV/DeepFace:** Both are used for face recognition; select via UI dropdown
- **PyQt6:** All UI logic is built with PyQt6 widgets and layouts.

## Patterns & Examples
- **Add new photo attribute:** Update DB schema in `core/database.py`, normalization in `core/ai_analyzer.py`, and UI in `nova_manager.py`.
- **Face matching:** Use `FaceMatcherV2` class in `core/face_matcher_v2.py` for OpenCV, or `FaceMatcherDeepFace` in `core/face_matcher_deepface.py`.
- **Batch update:** Use the GUI's batch update feature or extend `scripts/publish_tab_method.py` for custom logic.

## Key Files
- Main app: [nova_manager.py](nova_manager.py)
- Core modules: [core/database.py](core/database.py), [core/ai_analyzer.py](core/ai_analyzer.py)
- Face matching: [core/face_matcher_v2.py](core/face_matcher_v2.py), [core/face_matcher_deepface.py](core/face_matcher_deepface.py)
- Requirements: [requirements.txt](requirements.txt)
- Tests: [tests/test_face_matcher_v2.py](tests/test_face_matcher_v2.py), [tests/test_window.py](tests/test_window.py)

---
**Feedback:** If any section is unclear or missing, please specify which workflows, conventions, or integration details need more coverage.
- Tests: [test_face_matcher_v2.py](test_face_matcher_v2.py), [test_window.py](test_window.py)

---
**Feedback:** If any section is unclear or missing, please specify which workflows, conventions, or integration details need more coverage.

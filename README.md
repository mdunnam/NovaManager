# PhotoFlow

A general-purpose photo organizer and multi-platform social publisher — built with Python, PyQt6, and local AI (LLaVA/Ollama).

## Features

- **AI-Powered Analysis**: Automatically analyzes photos using LLaVA vision model — scene type, mood, subjects, colors, objects, captions, and hashtags
- **EXIF Extraction**: Camera, lens, ISO, aperture, shutter speed, focal length, GPS coordinates, and date taken
- **Duplicate Detection**: Exact (MD5) and near-duplicate (perceptual hash) detection with side-by-side review
- **Quality Scoring**: Blur and exposure assessment for every photo
- **Albums & Collections**: Manual albums and smart/date-based albums with cover photo support
- **Workflow Status**: Track photos as Unreviewed → Editing → Ready → Published
- **Multi-Platform Publishing**: Schedule and post to Instagram, TikTok, Twitter, Facebook, Pinterest, Threads
- **Batch Operations**: Update metadata, status, and packages for multiple photos at once
- **Folder Watcher**: Automatically detects and imports new photos added to your folder
- **Filtering**: Filter photos by status, scene, mood, subjects, quality, EXIF, GPS, content rating, and more
- **Image Retoucher**: Blemish removal with annotated canvas, layers, undo history, and project save/load

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Ollama and pull the LLaVA model (optional — required for AI analysis):
```bash
ollama pull llava
```

3. Run the application:
```bash
python photoflow.py
```

## Usage

1. **Select Root Folder**: Choose the folder containing your images
2. **Include Subfolders**: Check this option to scan subdirectories
3. **Analyze Images**: Click "Analyze Images" to run AI analysis on all photos
4. **Browse & Filter**: Use Gallery, Library, and Filters tabs to explore your photos
5. **Albums**: Organize photos into manual or smart (date-based) albums
6. **Publish**: Schedule and post to social platforms via the Publish, Instagram, and TikTok tabs

## Database

All metadata is stored in a SQLite database at `data/photos.db` (auto-created on first run).

## Project Structure

```
PhotoFlow/
├── photoflow.py             # Main application entry point
├── nova_manager.py          # Core application module (imported by photoflow.py)
├── core/                    # Core business logic
│   ├── database.py          # SQLite database management
│   ├── ai_analyzer.py       # AI photo analysis (LLaVA/Ollama)
│   ├── exif_extractor.py    # EXIF metadata extraction
│   ├── duplicate_detector.py# MD5 + perceptual hash deduplication
│   ├── quality_scorer.py    # Blur + exposure scoring
│   ├── folder_watcher.py    # Auto-import new files
│   └── image_retoucher.py   # Inpainting / blemish removal
├── ui/                      # PyQt6 tab widgets
├── data/                    # Runtime data (database, logs)
├── scripts/                 # Utility scripts
├── tests/                   # Test files
├── docs/                    # Documentation
└── themes/                  # QSS stylesheets
```

## Fields Tracked

- Scene type, composition, subjects, dominant colors, detected objects
- Mood, location, content rating
- AI-generated caption and suggested hashtags
- EXIF: camera, lens, focal length, ISO, aperture, shutter speed, GPS, date taken
- Workflow status: Unreviewed → Editing → Ready → Published
- Platform release status (Instagram, TikTok, and more)
- Quality score (blur, exposure), perceptual hash for deduplication
- Tags, notes, package name, albums
- Dates

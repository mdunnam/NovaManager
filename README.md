# Nova Photo Manager

A desktop application for managing and organizing Nova's photo collection with AI-powered analysis.

## Features

- **AI-Powered Analysis**: Automatically analyzes photos using LLaVA vision model
- **Metadata Management**: Track shot type, pose, clothing, location, and more
- **Workflow Status**: Mark photos as needing editing, ready, or released to various platforms
- **Batch Operations**: Update multiple photos at once
- **Package Management**: Organize photos into named packages
- **Filtering**: Easily filter photos by status or attributes

## Installation

1. Install Python dependencies:
```bash
pip install PyQt6 Pillow ollama
```

2. Install Ollama and pull the LLaVA model:
```bash
ollama pull llava
```

3. Run the application:
```bash
python nova_manager.py
```

## Usage

1. **Select Root Folder**: Choose the folder containing your images
2. **Include Subfolders**: Check this option to scan subdirectories
3. **Analyze Images**: Click "Analyze Images" to process all photos
4. **View Results**: Browse analyzed photos in the table
5. **Batch Update**: Select multiple photos and apply status updates
6. **Filter**: Use the Filters tab to view specific subsets of photos

## Database

The application stores all metadata in a SQLite database at:
`nova_photos.db` (in project root)

## Project Structure

```
NovaApp/
├── nova_manager.py          # Main application entry point
├── core/                    # Core business logic
│   ├── database.py         # SQLite database management
│   ├── ai_analyzer.py      # AI-powered image analysis
│   ├── face_matcher_v2.py  # OpenCV face matching
│   └── face_matcher_deepface.py  # DeepFace face matching
├── ui/                      # PyQt6 UI components
├── models/                  # AI model files
├── scripts/                 # Utility scripts
├── tests/                   # Test files
├── docs/                    # Documentation
└── themes/                  # UI themes
```

## Fields Tracked

- Shot type (selfie, portrait, fullbody, closeup)
- Pose (standing, sitting, lying, kneeling, leaning)
- Facing direction (atcamera, away, up, down, left, right, side, back)
- Explicit level (sfw, mild, suggestive, explicit)
- Clothing color, material, and type
- Footwear
- Interior/Exterior
- Location
- Workflow status (needs editing, ready, released to platforms)
- Package name
- Dates

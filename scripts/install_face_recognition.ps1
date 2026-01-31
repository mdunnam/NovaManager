# Installation script for face recognition solutions

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  NovaApp Face Recognition Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment is activated
if (-not $env:VIRTUAL_ENV) {
    Write-Host "⚠ Virtual environment not activated" -ForegroundColor Yellow
    Write-Host "Activating .venv..." -ForegroundColor Yellow
    & "H:\NovaApp\.venv\Scripts\Activate.ps1"
}

Write-Host ""
Write-Host "Choose installation option:" -ForegroundColor Green
Write-Host "1. OpenCV only (lightweight, fast, ~50MB)" -ForegroundColor White
Write-Host "2. DeepFace (most accurate, ~500MB with TensorFlow)" -ForegroundColor White
Write-Host "3. Both (recommended for testing)" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Enter choice (1, 2, or 3)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "Installing OpenCV solution..." -ForegroundColor Cyan
        pip install opencv-python opencv-contrib-python numpy Pillow
        Write-Host ""
        Write-Host "✓ OpenCV installed!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Test with: python test_face_matcher_v2.py" -ForegroundColor Yellow
    }
    "2" {
        Write-Host ""
        Write-Host "Installing DeepFace solution..." -ForegroundColor Cyan
        Write-Host "(This may take a few minutes...)" -ForegroundColor Yellow
        pip install deepface tf-keras tensorflow opencv-python numpy Pillow
        Write-Host ""
        Write-Host "✓ DeepFace installed!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Test with: python test_deepface.py" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Note: First run will download model files (~100-200MB)" -ForegroundColor Yellow
    }
    "3" {
        Write-Host ""
        Write-Host "Installing both solutions..." -ForegroundColor Cyan
        Write-Host "(This may take a few minutes...)" -ForegroundColor Yellow
        pip install deepface tf-keras tensorflow opencv-python opencv-contrib-python numpy Pillow
        Write-Host ""
        Write-Host "✓ Both solutions installed!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Test OpenCV: python test_face_matcher_v2.py" -ForegroundColor Yellow
        Write-Host "Test DeepFace: python test_deepface.py" -ForegroundColor Yellow
    }
    default {
        Write-Host ""
        Write-Host "✗ Invalid choice" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "1. Read FACE_RECOGNITION_GUIDE.md for usage examples" -ForegroundColor White
Write-Host "2. Run a test script to verify installation" -ForegroundColor White
Write-Host "3. Integrate with your NovaApp" -ForegroundColor White
Write-Host ""

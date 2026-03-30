# PhotoFlow — Master Plan
**App:** PhotoFlow (entry point: `photoflow.py`)
**Stack:** Python · PyQt6 · SQLite · LLaVA/Ollama · Social APIs
**Last updated:** 2026-03-29

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Phase 1 — Core Generalization](#phase-1--core-generalization)
3. [Phase 2 — Photo Organization](#phase-2--photo-organization)
4. [Phase 3 — Social Media Publishing](#phase-3--social-media-publishing)
5. [Phase 4 — AI Enhancements](#phase-4--ai-enhancements)
6. [Phase 5 — Power User Features](#phase-5--power-user-features)
7. [Phase 6 — Performance & Polish](#phase-6--performance--polish)
8. [Tab Layout](#tab-layout)
9. [Database Schema](#database-schema)
10. [Implementation Priority Table](#implementation-priority-table)
11. [Dependencies](#dependencies)
12. [File Map](#file-map)
13. [Risk Log](#risk-log)
14. [Success Metrics](#success-metrics)

---

## Architecture Overview

```
photoflow.py              ← entry point (delegates to nova_manager.py today)
nova_manager.py           ← MainWindow + all workflow logic (~6000 lines)
core/
  database.py             ← SQLite CRUD + migrations + encryption
  ai_analyzer.py          ← LLaVA/Ollama photo analysis
  exif_extractor.py       ← EXIF metadata reading
  duplicate_detector.py   ← MD5 + perceptual hash dedup
  quality_scorer.py       ← blur + exposure scoring
  folder_watcher.py       ← watchdog auto-import
  image_retoucher.py      ← inpainting / blemish removal
  icons.py                ← icon helper
  social/                 ← per-platform API clients + scheduler
ui/                       ← PyQt6 tab widgets (one file per tab)
themes/                   ← QSS stylesheets
data/                     ← runtime: photos.db, logs, caches
```

### What Stays Permanently
| Component | Reason |
|-----------|--------|
| `AnnotatedImageCanvas` | World-class pan/zoom, layers, tablet support, undo |
| `PhotoDatabase` core CRUD | All CRUD + migration reusable |
| `CredentialEncryption` | Solid Fernet machine-key encryption |
| `posting_history` table | Already platform-agnostic |
| Gallery tab grid view | Generic, looks great |
| Image retoucher | Blemish removal useful for all photos |
| QSettings persistence | Window state/prefs |
| Thumbnail caching | In place and working |
| PyQt6 tab architecture | Solid, just rearrange tabs |

### What Was Removed (Nova-specific)
- `explicit_level`, `released_fansly`, `date_released_fansly` columns (hidden, not deleted)
- `face_matching_tab.py`, `learning_tab.py`, `vocabularies_tab.py` removed from tab bar
- Nova persona face matching UI hidden
- Adult content vocabulary management hidden

---

## Phase 1 — Core Generalization
**Status: ✅ COMPLETE**

| Task | Status |
|------|--------|
| 1.1 App rename (`photoflow.py` entry point, window title "PhotoFlow") | ✅ Done |
| 1.1 Update README entry point to `python photoflow.py` | ✅ Done |
| 1.2 DB schema migration — new columns (scene_type, EXIF, platform_status, etc.) | ✅ Done |
| 1.2 DB — `albums`, `album_photos`, `scheduled_posts` tables created | ✅ Done |
| 1.3 Generalize AI analyzer prompt (scene, mood, subjects, colors, caption) | ✅ Done |
| 1.3 Remove adult-content vocabulary constraints from prompt | ✅ Done |
| 1.4 Photos Tab — new columns (scene_type, mood, subjects, location, objects) | ✅ Done |
| 1.5 Filters Tab — scene, mood, subjects, quality, EXIF, GPS, content_rating | ✅ Done |
| 1.6 Remove Face Match, AI Learning, Vocabularies tabs from tab bar | ✅ Done |
| 1.7 Publish Tab — add Pinterest + Threads stage buttons | ✅ Done |
| 1.7 Vocabularies field list updated to general fields | ✅ Done |

---

## Phase 2 — Photo Organization
**Status: 🔲 Not started**
**Estimated sessions: 3–4**

### 2.1 Albums & Collections
- [ ] `AlbumsTab` sidebar list of albums
- [ ] Drag photos from Gallery into albums
- [ ] Right-click photo → "Add to Album"
- [ ] Album cover photo (click to set)
- [ ] Manual sort order drag-and-drop
- [ ] Smart Albums — auto-populated by filter criteria:
  - By month/year (e.g. "March 2026")
  - By scene_type (e.g. "Landscapes")
  - By platform status (e.g. "Ready to Post")
  - User-defined JSON filter as smart album criteria
- [ ] Album detail view (grid of album's photos)
- [ ] Rename / delete albums with confirmation

### 2.2 EXIF Panel
- [ ] EXIF extraction on import (already has `exif_extractor.py`)
- [ ] Display EXIF in gallery detail view (right panel)
- [ ] GPS lat/lon display with copy button
- [ ] Optional: open location in system maps (Google Maps URL)
- [ ] Group Gallery photos by `exif_date_taken` (date section headers)

### 2.3 Duplicate Detection
- [ ] Perceptual hash (`imagehash`) computed on import
- [ ] MD5 exact duplicate check (already has `hashlib`)
- [ ] "Find Duplicates" tool — groups photos by hash, side-by-side compare
- [ ] User picks which copy to keep; others marked duplicate or deleted
- [ ] Batch-keep largest file / newest file options
- [ ] `DuplicatesTab` already scaffolded but needs full implementation

### 2.4 Smart Auto-Grouping in Gallery
- [ ] "Group by Date" — month/year section separators
- [ ] "Group by Location" — cluster by EXIF GPS bounding box
- [ ] "Group by Scene" — sections by `scene_type`
- [ ] Toggle grouped/flat view in gallery toolbar

### 2.5 Folder Watcher
- [ ] `FolderWatcher` using `watchdog` (already in `core/folder_watcher.py`)
- [ ] Watch configured root folder for new image files
- [ ] Auto-import new files to database on detection
- [ ] Optionally auto-analyze with AI on import
- [ ] Status bar notification: "3 new photos detected"
- [ ] Settings toggle: watch on/off + path config

### 2.6 Full-Text Search
- [ ] Persistent search bar in toolbar (all tabs)
- [ ] Searches: filename, notes, tags, location, objects_detected, ai_caption
- [ ] Search history dropdown (last 10)
- [ ] Tag cloud view — click tag to filter
- [ ] SQLite FTS5 virtual table for fast full-text queries

### 2.7 Batch File Operations
- [x] Batch rename — pattern: `{date}_{scene}_{index}`
- [x] Batch resize — target dimensions or max KB
- [x] Batch format convert (PNG → JPG, HEIC → JPG, etc.)
- [x] Export to folder — copy selected photos to destination
- [x] Watermark applicator — text or image overlay
- [x] Strip EXIF (privacy tool — remove GPS/camera data)
- [ ] Lossless rotation by EXIF orientation

### 2.8 Map View *(New Idea)*
- [ ] Photos with GPS data plotted on an embedded map widget
- [ ] Click pin on map to open photo
- [ ] Cluster nearby pins when zoomed out
- [ ] Uses `folium` (renders to HTML widget) or `PyQtWebEngine` with Leaflet.js
- [ ] Toggle map view in Gallery toolbar

### 2.9 Calendar View *(New Idea)*
- [ ] Monthly calendar showing thumbnails on the day they were taken
- [ ] Click day to open filtered gallery for that date
- [ ] Color-coded by scene type or platform status
- [ ] Navigate month/year with arrows

### 2.10 Collections / Mood Boards *(New Idea)*
- [ ] "Mood Board" canvas — drag photos into a free-form layout
- [ ] Resize, overlap, add text labels
- [ ] Save/export as flat image (PNG)
- [ ] Useful for composing Instagram carousels, lookbooks, etc.

---

## Phase 3 — Social Media Publishing
**Status: 🔲 Not started**
**Estimated sessions: 5–7**

### Platform Priority

| Platform | Priority | API | Auth | Post Types |
|----------|----------|-----|------|------------|
| Instagram | P0 | Graph API (Business/Creator) | OAuth2 | Feed, Reel, Story, Carousel |
| TikTok | P0 | TikTok for Developers | OAuth2 | Video, Photo |
| Twitter/X | P1 | API v2 | OAuth2 PKCE | Tweet + media |
| Facebook | P1 | Graph API (Pages) | OAuth2 | Post, Story |
| Pinterest | P2 | Pinterest API v5 | OAuth2 | Pin |
| Threads | P2 | Threads API | OAuth2 | Thread post |

### 3.1 Settings / Connections Tab
- [ ] Per-platform connection cards (icon, name, connect/disconnect button)
- [ ] OAuth browser flow → save tokens via `CredentialEncryption`
- [ ] Connection status + last verified timestamp
- [ ] Credential health check (test API call on open)
- [ ] AI settings: Ollama URL, model selector, temperature slider

### 3.2 Instagram Graph API
- [ ] OAuth2 + Facebook Developer App setup guide in UI
- [ ] Media container upload → publish flow
- [ ] Post types: Feed, Reel, Story, Carousel (multi-image)
- [ ] Caption + hashtags + location tag
- [ ] Alt text field for accessibility
- [ ] Insight pull-back: likes, comments, reach (if API permits)

### 3.3 TikTok API
- [ ] OAuth2 PKCE auth flow
- [ ] Video upload with caption + hashtags
- [ ] Photo post (TikTok photo mode)
- [ ] Privacy settings (everyone / friends / private)
- [ ] Duet / stitch flags

### 3.4 Twitter/X API
- [ ] OAuth2 PKCE
- [ ] Chunked media upload for large images
- [ ] Tweet creation with `media_ids`
- [ ] Character limit counter (280)
- [ ] Alt text for images
- [ ] Thread composer (multi-tweet)

### 3.5 Facebook Pages API
- [ ] OAuth2 + `pages_manage_posts` permission
- [ ] Upload photo to page feed with caption
- [ ] Fetch user's Pages list in settings
- [ ] Schedule post via Graph API (`published=false` + `scheduled_publish_time`)

### 3.6 Pinterest API
- [ ] OAuth2 flow
- [ ] Board selector (fetch user boards)
- [ ] Pin creation: title, description, link, alt text
- [ ] Board creation from within app

### 3.7 Multi-Platform Post Composer
- [ ] `ComposerTab` — select photo(s) from library
- [ ] Platform checkboxes (post to multiple simultaneously)
- [ ] Per-platform caption editor (tabbed: Instagram / Twitter / Pinterest…)
- [ ] Shared hashtag pool + per-platform overrides
- [ ] Character limit indicators
- [ ] Basic post preview mockup (phone frame)
- [ ] "Post Now" + "Schedule" buttons
- [ ] AI "Suggest Caption" button per platform

### 3.8 Post Scheduler
- [ ] `SchedulerWorker` QThread checks `scheduled_posts` every minute *(already scaffolded)*
- [ ] Status flow: pending → sending → posted / failed
- [ ] Retry logic: max 3, exponential backoff
- [ ] `ScheduleTab` calendar view — upcoming / past
  - Platform status icons per post
  - Edit / cancel / retry buttons
  - Filter by platform

### 3.9 Post Queue Manager (Publish Tab)
- [ ] Queue of "ready" photos per platform *(Publish tab already has list)*
- [ ] Drag-to-reorder queue
- [ ] Bulk schedule (X photos spread over Y days at Z time)
- [ ] One-click "Post Next in Queue"

### 3.10 Posting History
- [ ] Clickable post URL
- [ ] Thumbnail of posted photo
- [ ] Caption used + hashtags
- [ ] Basic engagement stats pull-back if API supports it

### 3.11 Cross-Post Analytics Dashboard *(New Idea)*
- [ ] Aggregate view — total posts per platform per week
- [ ] Bar chart: posts vs. engagement (likes + comments)
- [ ] Best performing posts (sorted by engagement)
- [ ] Best day / time of week heatmap
- [ ] Uses `matplotlib` embedded via `FigureCanvasQTAgg` or simple QLabel chart

### 3.12 Caption Template Library *(New Idea)*
- [x] Save reusable caption templates with `{caption}`, `{hashtags}`, `{photo_date}` tokens
- [x] Per-platform templates
- [x] Template picker in ComposerTab
- [ ] Import/export templates as JSON
- [x] Shared placeholders: location, mood, scene, detected objects auto-filled

---

## Phase 4 — AI Enhancements
**Status: 🔲 Not started**
**Estimated sessions: 2–3**

### 4.1 General Scene Analysis (Reprompted LLaVA)
Current prompt already covers:
- scene_type, composition, subjects, dominant_colors, objects_detected, mood
- ai_caption, suggested_hashtags, content_rating, location
- image_quality rating

### 4.2 Caption Generator
- [ ] "Generate Caption" button in gallery detail view
- [ ] Per-platform variants:
  - Instagram: casual, emoji-friendly, up to 2200 chars
  - Twitter: witty, ≤280 chars
  - Pinterest: descriptive, SEO keyword-rich
  - Facebook: conversational, longer-form OK
- [ ] User can accept / edit / regenerate
- [ ] Saved to `ai_caption` field

### 4.3 Hashtag Suggestions
- [ ] Generated from objects + scene + mood
- [ ] Platform-aware count (Instagram ≤30, Twitter 2-3)
- [ ] User-maintained hashtag sets (saved per topic, e.g. "travel", "food")
- [ ] "Copy hashtags" one-click button

### 4.4 Image Quality Scoring
- [ ] Blur detection: Laplacian variance (OpenCV)
- [ ] Exposure check: histogram analysis (Pillow)
- [ ] Composition score: rule-of-thirds subject placement
- [ ] Quality badge: ⭐ Excellent / ✓ Good / ⚠ Fair / ✗ Poor
- [ ] Show in gallery thumbnail corner + photos table
- [ ] Filter by quality in Filters tab

### 4.5 Best Time to Post
- [ ] Rules-based per-platform recommendations shown in Scheduler
- [ ] Eventually: pull from platform analytics API

### 4.6 AI Background Removal *(New Idea)*
- [ ] One-click background removal using `rembg` library (U²-Net model, local)
- [ ] Result shown as layer on `AnnotatedImageCanvas`
- [ ] Export as PNG with transparent background
- [ ] Useful for product shots, profile photos

### 4.7 Auto-Tagging Improvements *(New Idea)*
- [ ] Confidence score per AI tag shown in detail panel
- [ ] Low-confidence tags highlighted in orange — user prompted to confirm
- [ ] "Reject tag" action saves negative example for future correction learning
- [x] Tag suggestions as you type in the tags field (autocomplete from existing tags)

### 4.8 Similar Photos Finder *(New Idea)*
- [ ] Embed all photos with a compact visual feature vector (CLIP or LLaVA embed mode)
- [ ] "Find Similar" button on any photo → shows top N visually similar results
- [ ] Useful for finding near-duplicates that differ only in crop/color
- [ ] Powered by cosine similarity on stored embeddings (saved in DB)

### 4.9 Smart Auto-Albums *(New Idea)*
- [ ] AI groups photos automatically: "Birthday Party 2025", "Paris Trip"
- [ ] Groups by date + location + scene clustering
- [ ] User reviews suggested groupings + confirms or adjusts
- [ ] Runs as background job after import

### 4.10 Alt Text Generator *(New Idea)*
- [x] Auto-generate accessibility alt text for each photo
- [x] Uses LLaVA — terse, descriptive, screen-reader friendly
- [x] Shown in gallery detail panel with one-click generate button
- [x] Saved to new `alt_text` DB column

---

## Phase 5 — Power User Features
**Status: 🔲 Not started**
**Estimated sessions: 4–5**

### 5.1 Keyboard Shortcut System
- [ ] Fully documented shortcut map shown in Help → Keyboard Shortcuts
- [ ] Arrow keys navigate photos in gallery
- [ ] `Space` = quick approve (mark Ready)
- [ ] `R` = reject (mark Unreviewed)
- [ ] `E` = open editor
- [ ] `C` = open composer
- [ ] `Ctrl+A` = select all, `Ctrl+D` = deselect all
- [ ] `Delete` = move selected to trash (with undo)
- [ ] `/` = focus search bar

### 5.2 Photo Trash / Soft Delete
- [ ] "Move to Trash" instead of permanent delete
- [ ] Trash tab showing deleted photos for 30 days
- [ ] "Restore" restores to original location + DB record
- [ ] "Empty Trash" permanently deletes files
- [ ] Auto-empty after configurable retention period

### 5.3 Custom Metadata Fields *(New Idea)*
- [ ] User can define their own metadata fields (name, type: text/number/dropdown/date)
- [ ] Fields shown in gallery detail panel + photos table (optional column)
- [ ] Stored as JSON in a `custom_metadata` column per photo
- [ ] Filterable in Filters tab

### 5.4 Plugin / Script API *(New Idea)*
- [x] Simple Python plugin system: drop `.py` file in `plugins/` folder
- [x] Plugin defines: name, menu label, `run(photos, db)` function
- [x] Example plugin: export CSV
- [x] Plugins listed in Tools menu with one-click run
- [x] Bad plugin errors shown in dialog, never crash the app

### 5.5 Import Profiles *(New Idea)*
- [x] Named import presets: "Vacation Photos" (auto-tag travel), "Product Shoot" (auto-tag product)
- [x] Profile sets: auto-analysis on/off, default tags, default album, default status
- [x] Applied at scan time via dropdown in top toolbar
- [ ] Import history log showing which profile was used

### 5.6 Stash / Quick Collection *(New Idea)*
- [x] Temporary holding area — "Stash" — for photos you're currently working on
- [x] One-click "Stash / Unstash" button in Gallery detail panel
- [x] Stash stored as a singleton album (`__stash__`) in the DB
- [x] Clear stash when done; photos remain in library
- [ ] Stash badge on tab showing count

### 5.7 Smart Rename Rules *(New Idea)*
- [ ] Filename pattern builder using tokens:
  - `{date_taken}`, `{scene_type}`, `{location}`, `{mood}`, `{id}`, `{original_name}`
- [ ] Live preview of new filename before applying
- [ ] Saved rename rules (pick from list)
- [ ] Applied to checked photos in Batch tab

### 5.8 Print Layout Builder *(New Idea)*
- [ ] Arrange selected photos on A4/letter canvas for printing
- [ ] Pick from pre-defined layouts: contact sheet, 4x6, 5x7, wallet
- [ ] Add captions below each photo
- [ ] Export as PDF for printing or sharing

### 5.9 Cloud Backup Integration *(New Idea)*
- [ ] Optional sync of `photos.db` to a cloud provider (Dropbox, OneDrive, Google Drive)
- [ ] Syncs the database only (metadata), not the actual image files
- [ ] Restores DB on new machine from cloud backup
- [ ] Manual "Backup Now" + automatic on close

### 5.10 Multi-Account Social Support *(New Idea)*
- [ ] Multiple Instagram / TikTok accounts stored separately
- [ ] Account switcher in per-platform tab header
- [ ] Posting history scoped per account
- [ ] Useful for managing multiple brands/clients

### 5.11 Notes & Journal *(New Idea)*
- [ ] Per-photo long-form notes already in DB
- [ ] New: global Journal tab — day-by-day entries linked to photos taken that day
- [ ] Journal entry auto-created with thumbnails of photos from that date
- [ ] User can write notes about the shoot, context, story
- [ ] Export journal as PDF / HTML

### 5.12 Facial Recognition (General) *(New Idea — replaces Nova persona matcher)*
- [ ] Detect and cluster faces across library (no specific person required)
- [ ] Name face clusters: "Alice", "Bob" etc.
- [ ] Filter Gallery/Library by person
- [ ] Runs fully local (no cloud) using `face_recognition` or DeepFace
- [ ] Useful for family photo management, event photos

---

## Phase 6 — Performance & Polish
**Status: 🔲 Not started**
**Estimated sessions: 2–3**

### 6.1 Thumbnail Generation Pipeline
- [ ] Background thread pool for thumbnail creation on import
- [ ] Tiered thumbnail cache: 50 / 100 / 150px pre-generated
- [ ] Gallery lazy-loader: only render visible grid cells
- [ ] Progressive JPEG decode for faster first-display
- [ ] Cache invalidation when file is replaced/retouched

### 6.2 Database Performance
- [ ] Full-text search via SQLite FTS5 virtual table
- [ ] Compound indexes on commonly-filtered columns
- [ ] Pagination in `get_all_photos()` (virtual scroll for 10k+ photos)
- [x] WAL mode enabled for concurrent reads
- [x] Analyze / VACUUM scheduled weekly on startup

### 6.3 Startup Time
- [ ] Lazy-import heavy modules (cv2, DeepFace, imagehash)
- [ ] Background warm-up thread for Ollama connection check
- [ ] Splash screen while loading
- [ ] Recent folder remembered — skip folder picker on launch

### 6.4 Theme System
- [x] Light / Dark toggle in Preferences dialog (live preview)
- [ ] High-contrast accessibility theme
- [ ] Accent colour picker
- [ ] Font size scaler (small / medium / large)

### 6.5 Accessibility
- [ ] Tab-key navigation throughout all forms
- [ ] All icons have `toolTip` set
- [ ] Screen-reader-compatible labels on table columns
- [ ] Minimum contrast ratio compliance for status text colors

### 6.6 Crash Recovery
- [ ] Auto-save editing session every 5 minutes
- [ ] On crash: "Restore last session?" prompt on next launch
- [ ] Structured error log (`data/errors.log`) already in place — surface in Settings
- [ ] One-click "Report issue" that opens GitHub issues with log snippet pre-filled

### 6.7 Localisation / i18n *(New Idea)*
- [ ] `gettext`-based string extraction
- [ ] English (default), French, German, Spanish packs to start
- [ ] Locale auto-detected from OS, overridable in Settings
- [ ] Date/time formatted per locale

### 6.8 Onboarding Wizard *(New Idea)*
- [x] First-run wizard:
  1. Choose photo root folder
  2. Optionally connect first social account
  3. Choose whether to auto-analyze with AI
  4. Pick dark/light theme
- [x] "Quick Import" opens wizard if no photos in DB
- [x] Skippable — jump straight to empty library

---

## Tab Layout (Target)

```
[Gallery] [Library] [Albums] [Filters] [Duplicates] [Batch]
[Compose] [Schedule] [Publish] [Instagram] [TikTok] [Twitter] [Facebook] [Pinterest] [Threads]
[Settings]
```

Or with scrollable tab bar (current approach) in this preferred order:
```
Gallery → Library → Albums → Filters → Duplicates → Batch → Compose → Schedule → Publish →
Instagram → TikTok → Twitter → Facebook → Pinterest → Threads → History → Settings
```

---

## Database Schema

### `photos` table (key columns)
```sql
-- Identity
id, filepath, filename, date_added, date_created, date_modified

-- AI Analysis
scene_type, composition, subjects, dominant_colors, objects_detected,
mood, location, content_rating, ai_caption, alt_text, suggested_hashtags

-- EXIF
exif_camera, exif_lens, exif_focal_length, exif_iso, exif_aperture,
exif_shutter, exif_gps_lat, exif_gps_lon, exif_date_taken

-- File metadata
file_size_kb, image_width, image_height, color_profile,
perceptual_hash, file_hash

-- Workflow
status (unreviewed|editing|ready|published)
released_instagram, released_tiktok, platform_status (JSON)

-- Quality
blur_score, exposure_score, quality, quality_issues, quality_score

-- Organisation
package_name, tags, notes, custom_metadata (JSON)

-- Face recognition (future)
face_clusters (JSON)
```

### `albums` table
```sql
id, name, description, cover_photo_id, date_created, date_modified,
sort_order, is_smart (0/1), smart_filter (JSON)
```

### `album_photos` junction
```sql
album_id, photo_id, sort_order, date_added  — UNIQUE(album_id, photo_id)
```

### `scheduled_posts` table
```sql
id, photo_id, platform, caption, hashtags, post_type, scheduled_time,
status (pending|sending|posted|failed|cancelled),
error_message, post_url, post_id, date_created
```

### `api_credentials` table
```sql
platform, encrypted_data (Fernet), date_added, date_modified
-- platforms: instagram, tiktok, twitter, facebook, pinterest, threads
```

### `posting_history` table
```sql
photo_id, platform, post_type, caption, post_url, post_id,
date_posted, status, error_message
```

### `ai_corrections` table (learning)
```sql
photo_id, field_name, original_value, corrected_value, correction_date
```

### `caption_templates` table *(new)*
```sql
id, name, platform, template_text, date_created
```

### `custom_fields` table *(new)*
```sql
id, field_name, field_type (text|number|dropdown|date), options_json, sort_order
```

---

## Implementation Priority Table

| # | Phase | Task | Priority | Effort | Status |
|---|-------|------|----------|--------|--------|
| 1 | 1 | App rename + entry point | P0 | Small | ✅ Done |
| 2 | 1 | DB schema migration | P0 | Medium | ✅ Done |
| 3 | 1 | Generalize AI prompt | P0 | Medium | ✅ Done |
| 4 | 1 | Remove Nova-specific tabs | P0 | Small | ✅ Done |
| 5 | 1 | Update Photos tab columns | P0 | Medium | ✅ Done |
| 6 | 1 | Update Filters tab | P0 | Small | ✅ Done |
| 7 | 1 | Update Publish tab platforms | P0 | Small | ✅ Done |
| 8 | 2 | EXIF panel in gallery detail | P1 | Small | ✅ Done |
| 9 | 2 | Albums tab (manual) | P1 | Large | ✅ Done |
| 10 | 2 | Duplicate detection (full UI) | P1 | Medium | ✅ Done |
| 11 | 2 | Smart grouping in Gallery | P1 | Medium | ✅ Done |
| 12 | 2 | Full-text search bar | P1 | Small | ✅ Done |
| 13 | 2 | Batch file operations | P1 | Medium | ✅ Done |
| 14 | 2 | Folder watcher settings UI | P1 | Small | 🔲 |
| 15 | 2 | Map view (GPS photos) | P2 | Medium | 🔲 |
| 16 | 2 | Calendar view | P2 | Medium | 🔲 |
| 17 | 2 | Smart rename rules | P2 | Small | 🔲 |
| 18 | 2 | Photo trash / soft delete | P1 | Small | ✅ Done |
| 19 | 3 | Settings / connections tab | P0 | Medium | 🔲 |
| 20 | 3 | Instagram Graph API | P0 | Large | 🔲 |
| 21 | 3 | TikTok API | P0 | Large | 🔲 |
| 22 | 3 | Multi-platform composer | P0 | Large | 🔲 |
| 23 | 3 | Post scheduler (full) | P1 | Large | 🔲 |
| 24 | 3 | Twitter/X API | P1 | Large | 🔲 |
| 25 | 3 | Facebook API | P2 | Large | 🔲 |
| 26 | 3 | Pinterest API | P2 | Large | 🔲 |
| 27 | 3 | Analytics dashboard | P2 | Medium | 🔲 |
| 28 | 3 | Caption template library | P2 | Small | 🔲 |
| 29 | 4 | Caption generator (per-platform) | P1 | Small | 🔲 |
| 30 | 4 | Hashtag suggestions | P1 | Small | 🔲 |
| 31 | 4 | Image quality scoring | P2 | Medium | 🔲 |
| 32 | 4 | AI background removal | P2 | Medium | 🔲 |
| 33 | 4 | Similar photos finder | P2 | Large | 🔲 |
| 34 | 4 | Smart auto-albums (AI grouping) | P2 | Large | 🔲 |
| 35 | 4 | Alt text generator | P1 | Small | 🔲 |
| 36 | 5 | Keyboard shortcut system | P1 | Small | ✅ Done |
| 37 | 5 | Custom metadata fields | P2 | Medium | 🔲 |
| 38 | 5 | Plugin / script API | P3 | Large | 🔲 |
| 39 | 5 | Import profiles | P2 | Small | 🔲 |
| 40 | 5 | Stash / quick collection | P2 | Small | 🔲 |
| 41 | 5 | Print layout builder | P3 | Large | 🔲 |
| 42 | 5 | Cloud backup (DB sync) | P2 | Medium | 🔲 |
| 43 | 5 | Multi-account social support | P2 | Medium | 🔲 |
| 44 | 5 | Facial recognition (general) | P2 | Large | 🔲 |
| 45 | 5 | Notes & journal tab | P3 | Medium | 🔲 |
| 46 | 6 | Thumbnail pipeline optimisation | P1 | Medium | 🔲 |
| 47 | 6 | SQLite FTS5 + pagination | P1 | Medium | 🔲 |
| 48 | 6 | Startup speed improvements | P2 | Small | 🔲 |
| 49 | 6 | Light/dark theme toggle | P1 | Small | 🔲 |
| 50 | 6 | Onboarding wizard | P2 | Medium | 🔲 |
| 51 | 6 | Crash recovery / session restore | P2 | Small | 🔲 |
| 52 | 6 | Localisation / i18n | P3 | Large | 🔲 |

---

## Dependencies

### Current (requirements.txt)
```
PyQt6
Pillow
opencv-python
numpy
requests
cryptography
ollama
imagehash
watchdog
requests-oauthlib
tweepy
```

### To Add As Needed
```
# Phase 2
folium               # Map view (GPS photos) — renders to HTML
pyqtwebengine        # Embed web content (map, calendar)

# Phase 3
facebook-sdk         # Facebook Graph API helper
pinterest-api        # Pinterest API v5 client

# Phase 4
rembg                # AI background removal (U²-Net, local)
# clip / sentence-transformers  # Similar photos feature vector (optional)

# Phase 5
reportlab            # PDF export (print layout builder)

# Phase 6
babel                # i18n / locale formatting
```

---

## File Map

### Existing (to keep / extend)
```
photoflow.py                      ← entry point
nova_manager.py                   ← MainWindow (refactor into smaller modules over time)
core/
  database.py                     ← extend with caption_templates, custom_fields tables
  ai_analyzer.py                  ← extend with alt_text, embedding generation
  exif_extractor.py               ← ✅ in place
  duplicate_detector.py           ← ✅ in place — needs DuplicatesTab wiring
  quality_scorer.py               ← ✅ in place
  folder_watcher.py               ← ✅ in place — needs Settings UI wiring
  image_retoucher.py              ← keep as-is
  social/
    scheduler.py                  ← ✅ in place — extend with retry logic
    instagram_api.py              ← stub → real implementation
    tiktok_api.py                 ← stub → real implementation
    twitter_api.py                ← stub → real implementation
    facebook_api.py               ← stub → real implementation
    pinterest_api.py              ← stub → real implementation
    threads_api.py                ← stub → real implementation
ui/
  gallery_tab.py                  ← extend: group by date/scene, map toggle
  photos_tab.py                   ← extend: keyboard nav, quality column
  filters_tab.py                  ← extend: face cluster filter, custom field filter
  albums_tab.py                   ← scaffold → full implementation
  composer_tab.py                 ← scaffold → full implementation
  schedule_tab.py                 ← scaffold → full implementation
  settings_tab.py                 ← scaffold → full implementation
  duplicates_tab.py               ← scaffold → full implementation
  publish_tab.py                  ← extend: all 6 platforms staged
  history_tab.py                  ← extend: thumbnails, engagement stats
  batch_tab.py                    ← extend: rename, resize, convert, watermark
  instagram_tab.py                ← → real API implementation
  tiktok_tab.py                   ← → real API implementation
```

### To Create
```
ui/
  twitter_tab.py                  ← Twitter/X post UI
  facebook_tab.py                 ← Facebook Pages post UI
  pinterest_tab.py                ← Pinterest pin UI
  threads_tab.py                  ← Threads post UI
  analytics_tab.py                ← Cross-platform analytics dashboard
  stash_tab.py                    ← Quick collection / scratchpad
  journal_tab.py                  ← Notes & journal (Phase 5)
core/
  caption_templates.py            ← Template CRUD helpers
  face_clusterer.py               ← General facial clustering (Phase 5)
plugins/
  __init__.py
  README.md                       ← Plugin API documentation
```

### Hidden (not deleted — keep for backward-compat)
```
ui/face_matching_tab.py           ← hidden from tab bar
ui/learning_tab.py                ← hidden from tab bar
ui/vocabularies_tab.py            ← hidden (may simplify + re-add to Settings)
core/face_matcher_v2.py           ← hidden — may reuse for general face clustering
core/face_matcher_deepface.py     ← hidden — may reuse for general face clustering
```

---

## Risk Log

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Instagram Graph API requires Business account | High | High | Document requirement; offer `instagrapi` as alternative |
| TikTok API approval is gated | Medium | High | Apply for developer access early |
| SQLite schema migration corrupts data | Low | High | Auto-backup DB before any migration; test on copy |
| LLaVA prompt changes break existing workflow | Low | Medium | Version the prompt; keep old prompt as fallback |
| OAuth flow complex in a desktop app | Medium | Medium | Use system browser + local `localhost` redirect server |
| `rembg` (background removal) is 200 MB model | Medium | Low | Download on first use; show progress; cache locally |
| Similar-photo embeddings slow on large libraries | Medium | Medium | Run as low-priority background job; index incrementally |
| Plugin API introduces security risk | Medium | Medium | Sandbox in subprocess; warn user before running unknown plugin |

---

## Success Metrics

### Phase 1 ✅
- [x] App runs without any Nova/adult-content-specific UI visible
- [x] Window title reads "PhotoFlow"
- [x] Entry point is `photoflow.py`

### Phase 2
- [x] User can import a folder of 1000 photos in under 60 seconds
- [x] Duplicate detection finds all exact duplicates in 1000-photo library
- [x] Albums support manual drag-and-drop + smart (date-based) auto-creation
- [ ] GPS photos visible on map view

### Phase 3
- [ ] User can post to Instagram with a single form + one button click
- [ ] User can schedule a post to appear at a future date
- [ ] Bulk scheduler can queue 30 posts across 30 days in < 1 minute
- [ ] Multi-platform composer posts to 3 platforms simultaneously

### Phase 4
- [ ] AI captions a photo in under 10 seconds (local LLaVA)
- [ ] Background removal produces usable result on simple subjects
- [ ] Similar photos finder returns results in < 3 seconds for 1000-photo library

### Phase 5
- [x] All primary actions reachable via documented keyboard shortcut
- [x] Trash/restore flow works with zero data loss
- [ ] Plugin system: example plugin runs successfully from `plugins/` folder

### Phase 6
- [ ] Gallery loads 500 photos without visible lag at 100px thumbnail size
- [ ] Cold start time < 3 seconds on target hardware
- [ ] App launches in dark mode matching system preference

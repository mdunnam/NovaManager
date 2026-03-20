# PhotoFlow — Pivot Plan
**From:** Nova AI Influencer Manager
**To:** General Photo Organizer + Multi-Platform Social Publisher
**Date:** 2026-03-20
**Stack:** Python · PyQt6 · SQLite · LLaVA/Ollama · Social APIs

---

## Executive Summary

NovaManager is a well-built ~13,000-line PyQt6 desktop app with solid bones:
annotated image canvas, encrypted credential storage, AI analysis via LLaVA,
SQLite with posting history, and stubs for Instagram/TikTok. The influencer-specific
framing (explicit content levels, Nova persona face matching, Fansly) is a thin layer
on top of genuinely useful general infrastructure.

The pivot keeps 90% of the code and replaces/extends the remaining 10% to produce
a polished general-audience photo organization + social publishing tool.

---

## What Stays (No Changes Needed)

| Component | Why |
|-----------|-----|
| `AnnotatedImageCanvas` | World-class inline editor — pan/zoom, layers, tablet support, undo |
| `PhotoDatabase` core CRUD | All add/update/delete/search logic reusable |
| `CredentialEncryption` | Solid Fernet-based encrypted credential store |
| `posting_history` table | Already platform-agnostic |
| `api_credentials` table | Already platform-agnostic |
| Gallery tab | Grid view is generic |
| Image retoucher | Blemish removal useful for any photo |
| QSettings persistence | Window state, preferences |
| Thumbnail caching system | Already in place |
| PyQt6 tab architecture | Solid, just rename/reorder tabs |

---

## What Gets Removed

| Item | Reason |
|------|--------|
| `explicit_level` field (sfw/mild/suggestive/explicit) | Not relevant to general audience |
| `released_fansly` + `date_released_fansly` columns | Adult platform, not general purpose |
| Fansly staging buttons in Publish tab | Same |
| `face_matching_tab.py` (Nova persona matching) | Persona-specific; not useful for general org |
| `face_matcher_v2.py` + `face_matcher_deepface.py` | Remove or repurpose (see Phase 2) |
| `learning_tab.py` | Nova-specific correction learning UI |
| `vocabularies_tab.py` | Adult content vocabulary management |
| Nova-specific AI prompt fields (pose, facing_direction, clothing, footwear, material) | Replace with general-purpose fields |
| "Nova" branding everywhere | Replace with new app name |

---

## What Gets Generalized

| Current | New |
|---------|-----|
| `type_of_shot` (selfie/portrait/fullbody) | `scene_type` (portrait, landscape, macro, street, event, food, product, travel, architecture, abstract) |
| `pose` + `facing_direction` | `subjects` (people, animals, none) + `composition` (closeup, wide, aerial, detail) |
| `color_of_clothing` + `material` + `type_clothing` + `footwear` | `dominant_colors` (comma-sep), `objects_detected` (comma-sep) |
| `location` (bed/beach/bath) | `location` (repopulated with general values: indoor, outdoor, urban, nature, studio, beach, mountain, etc.) |
| `status` workflow (raw→needs_edit→ready→released) | Keep but rename: `unreviewed→editing→ready→published` |
| `released_instagram` / `released_tiktok` | Generalize to JSON platform map (see DB schema below) |
| AI prompt (explicit-content-focused) | General scene analysis prompt |

---

## New App Name

Working name: **PhotoFlow**
Alternatives: SnapDeck, PixelDock, FrameKit

Action: Rename `nova_manager.py` → `photoflow.py`, update window title, README,
all in-code strings referencing "Nova".

---

## Database Schema Changes

### Modified: `photos` table

**Remove columns (migration):**
```sql
-- Cannot DROP in SQLite; migrate to new table approach
-- explicit_level, released_fansly, date_released_fansly,
-- pose, facing_direction, color_of_clothing, material,
-- type_clothing, footwear
```

**Add columns:**
```sql
ALTER TABLE photos ADD COLUMN scene_type TEXT DEFAULT '';
ALTER TABLE photos ADD COLUMN composition TEXT DEFAULT '';
ALTER TABLE photos ADD COLUMN subjects TEXT DEFAULT '';       -- comma-sep: people, animal, none
ALTER TABLE photos ADD COLUMN dominant_colors TEXT DEFAULT '';-- comma-sep: red, blue, etc.
ALTER TABLE photos ADD COLUMN objects_detected TEXT DEFAULT '';-- comma-sep AI-detected objects
ALTER TABLE photos ADD COLUMN mood TEXT DEFAULT '';           -- bright, dark, cozy, dramatic, etc.
ALTER TABLE photos ADD COLUMN exif_camera TEXT DEFAULT '';
ALTER TABLE photos ADD COLUMN exif_lens TEXT DEFAULT '';
ALTER TABLE photos ADD COLUMN exif_focal_length TEXT DEFAULT '';
ALTER TABLE photos ADD COLUMN exif_iso TEXT DEFAULT '';
ALTER TABLE photos ADD COLUMN exif_aperture TEXT DEFAULT '';
ALTER TABLE photos ADD COLUMN exif_shutter TEXT DEFAULT '';
ALTER TABLE photos ADD COLUMN exif_gps_lat REAL DEFAULT NULL;
ALTER TABLE photos ADD COLUMN exif_gps_lon REAL DEFAULT NULL;
ALTER TABLE photos ADD COLUMN exif_date_taken TIMESTAMP DEFAULT NULL;
ALTER TABLE photos ADD COLUMN content_rating TEXT DEFAULT 'general'; -- general, mature, restricted
ALTER TABLE photos ADD COLUMN ai_caption TEXT DEFAULT '';     -- AI-suggested caption
ALTER TABLE photos ADD COLUMN perceptual_hash TEXT DEFAULT '';-- for duplicate detection
ALTER TABLE photos ADD COLUMN file_size_kb INTEGER DEFAULT 0;
ALTER TABLE photos ADD COLUMN image_width INTEGER DEFAULT 0;
ALTER TABLE photos ADD COLUMN image_height INTEGER DEFAULT 0;
ALTER TABLE photos ADD COLUMN color_profile TEXT DEFAULT '';
ALTER TABLE photos ADD COLUMN platform_status TEXT DEFAULT '{}'; -- JSON: {"instagram": "posted", "twitter": "scheduled"}
```

### New: `albums` table
```sql
CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    cover_photo_id INTEGER REFERENCES photos(id),
    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sort_order INTEGER DEFAULT 0,
    is_smart INTEGER DEFAULT 0,  -- 0=manual, 1=smart/auto album
    smart_filter TEXT DEFAULT '' -- JSON filter criteria for smart albums
);

CREATE TABLE IF NOT EXISTS album_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id INTEGER REFERENCES albums(id) ON DELETE CASCADE,
    photo_id INTEGER REFERENCES photos(id) ON DELETE CASCADE,
    sort_order INTEGER DEFAULT 0,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(album_id, photo_id)
);
```

### New: `scheduled_posts` table
```sql
CREATE TABLE IF NOT EXISTS scheduled_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id INTEGER REFERENCES photos(id),
    platform TEXT NOT NULL,           -- instagram, twitter, facebook, pinterest, tiktok, threads
    caption TEXT DEFAULT '',
    hashtags TEXT DEFAULT '',
    post_type TEXT DEFAULT 'feed',    -- feed, story, reel, thread, pin, etc.
    scheduled_time TIMESTAMP NOT NULL,
    status TEXT DEFAULT 'pending',    -- pending, sending, posted, failed, cancelled
    error_message TEXT DEFAULT '',
    post_url TEXT DEFAULT '',
    post_id TEXT DEFAULT '',
    date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Updated: `api_credentials` platforms
Platforms supported: `instagram`, `tiktok`, `twitter`, `facebook`, `pinterest`, `threads`

---

## Phase 1 — Core Generalization
**Scope:** Strip influencer-specific, make app work for any photos
**Sessions:** 2–3
**Risk:** Low (mostly renaming + schema migration)

### Tasks

#### 1.1 App Rename & Rebranding
- [ ] Create `photoflow.py` as new entry point (rename `nova_manager.py`)
- [ ] Update `QMainWindow` title to "PhotoFlow"
- [ ] Update all strings: "Nova", "nova_photos.db" → "photos.db", etc.
- [ ] Update `README.md`
- [ ] Update window icon

#### 1.2 Database Schema Migration
- [ ] Write `PhotoDatabase.migrate_v2()` — adds all new columns, creates albums/scheduled_posts tables
- [ ] Remove explicit_level from all queries (keep column for old data compat, just hide it)
- [ ] Add EXIF extraction on photo import (use Pillow `_getexif()`)
- [ ] Add perceptual hash on import (use `imagehash` library or Pillow-based implementation)
- [ ] Add file_size, image dimensions on import

#### 1.3 Generalize AI Analyzer
- [ ] New prompt in `ai_analyzer.py` targeting: scene_type, composition, subjects, dominant_colors, objects_detected, mood, suggested_caption, suggested_hashtags
- [ ] Remove adult-content vocabulary constraints from prompt
- [ ] Update response parser for new fields
- [ ] Keep correction learning system (it's platform-agnostic)

#### 1.4 Update Photos Tab Columns
- [ ] Replace: type_of_shot, pose, facing_direction, explicit_level, clothing/material/footwear columns
- [ ] Add: scene_type, composition, subjects, mood, dominant_colors, exif_date_taken, file_size, dimensions
- [ ] Update batch operations for new fields
- [ ] Update filter dropdowns

#### 1.5 Update Filters Tab
- [ ] Remove: explicit_level filter, pose, facing_direction, clothing/material/footwear/footwear filters, Fansly filter
- [ ] Add: scene_type filter, subjects filter, mood filter, content_rating filter, has_EXIF filter, album filter

#### 1.6 Remove Nova-Specific Tabs
- [ ] Remove `face_matching_tab.py` from tab bar
- [ ] Remove `learning_tab.py` from tab bar
- [ ] Remove `vocabularies_tab.py` from tab bar (or simplify to Settings)
- [ ] Keep underlying code for now, just hide from UI

#### 1.7 Update Publish Tab
- [ ] Remove Fansly staging buttons
- [ ] Add Twitter, Facebook, Pinterest, Threads staging buttons
- [ ] Update release status tracking to use new `platform_status` JSON field

---

## Phase 2 — Photo Organization
**Scope:** Make it genuinely useful for organizing any photo library
**Sessions:** 3–4
**Risk:** Medium (new UI + features)

### Tasks

#### 2.1 Albums & Collections
- [ ] New `AlbumsTab` (replace Vocabularies tab)
  - Sidebar list of albums
  - Drag photos from Gallery into albums
  - Right-click photo → "Add to Album"
  - Album cover photo (click to set)
  - Sort album order manually
- [ ] Smart Albums (auto-populated by filter)
  - By month/year (e.g., "March 2026")
  - By scene_type (e.g., "Landscapes")
  - By platform status (e.g., "Ready to Post")
  - User-defined filter as smart album criteria

#### 2.2 EXIF Panel
- [ ] Add EXIF extraction on import (camera, lens, focal length, ISO, aperture, shutter, GPS, date taken)
- [ ] Display EXIF in gallery detail view (right panel)
- [ ] Display GPS on embedded map widget (or just show lat/lon with copy button)
- [ ] Group photos by `exif_date_taken` in Gallery (date headers)

#### 2.3 Duplicate Detection
- [ ] Compute perceptual hash (`imagehash` lib) on import
- [ ] New "Find Duplicates" tool: groups photos by hash, shows side-by-side
- [ ] User picks which copy to keep; others marked as duplicate or deleted
- [ ] Exact duplicate check by MD5 hash (already has `hashlib`)

#### 2.4 Smart Auto-Grouping
- [ ] "Group by Date" view in Gallery: month/year sections with separators
- [ ] "Group by Location" view: group by EXIF GPS cluster (simple bounding box)
- [ ] "Group by Scene" view: group by scene_type from AI analysis
- [ ] Toggle between grouped/flat view in gallery toolbar

#### 2.5 Folder Watcher
- [ ] New `FolderWatcher` class using `watchdog` library or polling thread
- [ ] Watch configured folder for new image files
- [ ] Auto-import new files to database
- [ ] Optionally auto-analyze with AI on import
- [ ] Show notification in status bar when new photos detected

#### 2.6 Better Search
- [ ] Full-text search across: filename, notes, tags, location, objects_detected, ai_caption
- [ ] Search bar in toolbar (persistent, across all tabs)
- [ ] Search history dropdown
- [ ] Tag cloud view (click tag to filter)

#### 2.7 Batch File Operations
- [ ] Batch rename (pattern-based: `{date}_{scene}_{index}`)
- [ ] Batch resize (target dimensions or max size in KB)
- [ ] Batch convert (PNG→JPG, etc.)
- [ ] Export to folder (copy selected photos to destination)
- [ ] Watermark applicator (text or image overlay)

---

## Phase 3 — Social Media Publishing
**Scope:** Real posting to multiple platforms, queue management, scheduling
**Sessions:** 5–7
**Risk:** High (API complexity, auth flows, rate limits)

### Platform Priority & API Strategy

| Platform | Priority | API | Auth Type | Post Types |
|----------|----------|-----|-----------|------------|
| Instagram | P0 | Graph API (Business/Creator) | OAuth2 | Feed, Reel, Story, Carousel |
| TikTok | P0 | TikTok for Developers API | OAuth2 | Video, Photo |
| Twitter/X | P1 | API v2 | OAuth2 + Bearer | Tweet w/ media |
| Facebook | P1 | Graph API (Pages) | OAuth2 | Post, Story |
| Pinterest | P2 | Pinterest API v5 | OAuth2 | Pin |
| Threads | P2 | Threads API | OAuth2 | Thread post |

### Tasks

#### 3.1 Platform Settings Tab (New Tab)
- [ ] New `SettingsTab` replacing current settings scattered in main window
- [ ] Per-platform connection cards:
  - Platform icon + name
  - "Connect" button → launches OAuth browser flow
  - Connected account name/avatar
  - "Disconnect" button
  - Connection status + last verified
- [ ] All credentials stored via existing `CredentialEncryption`

#### 3.2 Instagram Graph API (Real Implementation)
- [ ] OAuth2 flow via embedded browser or system browser
- [ ] Requires: Facebook Developer App + Instagram Business/Creator account
- [ ] Media upload: `POST /me/media` (container) → `POST /me/media_publish`
- [ ] Post types: Feed photo, Reel (video), Story (expires 24h), Carousel (multi-image)
- [ ] Caption + location + hashtags
- [ ] Alt text for accessibility
- [ ] Tag users in photo (optional)
- [ ] Update `instagram_tab.py` with real implementation

#### 3.3 Twitter/X API
- [ ] New `twitter_tab.py`
- [ ] OAuth2 PKCE flow
- [ ] Upload media: `POST /2/media/upload` (chunked for large files)
- [ ] Create tweet: `POST /2/tweets` with `media.media_ids`
- [ ] Character limit counter (280 chars)
- [ ] Alt text for images

#### 3.4 Facebook Pages API
- [ ] New `facebook_tab.py`
- [ ] OAuth2 with `pages_manage_posts` permission
- [ ] Upload photo: `POST /{page-id}/photos`
- [ ] Post to page feed with caption
- [ ] Fetch user's Pages list in settings

#### 3.5 Pinterest API
- [ ] New `pinterest_tab.py`
- [ ] OAuth2 flow
- [ ] Create pin: `POST /v5/pins`
- [ ] Select board from user's boards list
- [ ] Title, description, link, alt text

#### 3.6 Multi-Platform Post Composer
- [ ] New `ComposerTab` or modal dialog
- [ ] Select photo(s) from library
- [ ] Platform checkboxes (post to multiple at once)
- [ ] Per-platform caption editor (tabs for each platform)
- [ ] Shared hashtag pool + per-platform overrides
- [ ] Character limit indicators
- [ ] Preview how post will look (basic mockup)
- [ ] "Post Now" + "Schedule" buttons

#### 3.7 Post Scheduler
- [ ] `SchedulerWorker` (QThread) checks `scheduled_posts` table every minute
- [ ] Posts photos when `scheduled_time` is reached
- [ ] Status updates: pending → sending → posted / failed
- [ ] Retry logic (max 3 retries, exponential backoff)
- [ ] New `ScheduleTab` showing upcoming + past scheduled posts
  - Calendar view for upcoming posts
  - Status icons per post (pending/sent/failed)
  - Edit/cancel/retry buttons
  - Filter by platform

#### 3.8 Post Queue Manager (in Publish Tab)
- [ ] Redesign `publish_tab.py`
- [ ] Queue of "ready" photos staged for each platform
- [ ] Drag to reorder queue
- [ ] Bulk schedule (post X photos spread over Y days at Z time)
- [ ] One-click "Post Next in Queue"

#### 3.9 Posting History
- [ ] Enhance existing `posting_history` table + UI
- [ ] Show post URL as clickable link
- [ ] Show thumbnail of posted photo
- [ ] Show caption used
- [ ] Basic engagement stats (if API supports read-back)

---

## Phase 4 — AI Enhancements
**Scope:** Make AI actually useful for general photo workflow
**Sessions:** 2–3
**Risk:** Low (building on existing LLaVA integration)

### Tasks

#### 4.1 General Scene Analysis (Reprompted LLaVA)
New prompt targets:
```
Analyze this photo and return JSON with:
- scene_type: one of [portrait, landscape, street, event, food, product, travel, architecture, macro, abstract, sports, nature, night, interior]
- composition: one of [closeup, medium, wide, aerial, detail]
- subjects: comma-separated from [people, animal, vehicle, building, food, plant, sky, water, none]
- dominant_colors: top 3 colors as comma-separated color names
- mood: one of [bright, dark, dramatic, cozy, energetic, calm, romantic, mysterious, playful]
- objects_detected: up to 10 notable objects detected
- suggested_caption: A natural Instagram caption for this photo (1-2 sentences)
- suggested_hashtags: 10 relevant hashtags (no # prefix)
- image_quality: one of [excellent, good, fair, poor] based on sharpness/exposure/composition
```

#### 4.2 Caption Generator
- [ ] "Generate Caption" button in gallery detail view
- [ ] Per-platform prompt variants:
  - Instagram: casual, emoji-friendly
  - Twitter: concise, witty, ≤280 chars
  - Pinterest: descriptive, SEO-friendly
  - Facebook: conversational, longer-form OK
- [ ] User can accept/edit/regenerate
- [ ] Saved to `ai_caption` field

#### 4.3 Hashtag Suggestions
- [ ] Generate from detected objects + scene + mood
- [ ] Platform-aware (Instagram: up to 30; Twitter: 2-3; Pinterest: keyword phrases)
- [ ] Trending hashtag overlay (from external API, optional)
- [ ] User-maintained hashtag library (saved sets per topic)
- [ ] "Copy hashtags" button

#### 4.4 Image Quality Scoring
- [ ] Blur detection: Laplacian variance (OpenCV, already imported)
- [ ] Exposure check: histogram analysis via Pillow
- [ ] Composition score: rule-of-thirds subject placement estimate
- [ ] Overall quality badge: ⭐ Excellent / ✓ Good / ⚠ Fair / ✗ Poor
- [ ] Show in gallery thumbnail corner + photos table column
- [ ] Filter by quality in Filters tab

#### 4.5 Best Time to Post
- [ ] Simple rules-based per-platform recommendations
- [ ] Show in Scheduler when picking post time
- [ ] Eventually: pull from platform analytics API

---

## New Tab Layout

```
[Library] [Albums] [Compose] [Schedule] [Instagram] [TikTok] [Twitter] [Facebook] [Pinterest] [Settings]
```

- **Library** = current Gallery tab (generalized)
- **Albums** = new albums/collections UI
- **Compose** = multi-platform post composer
- **Schedule** = post queue + calendar view
- **Instagram/TikTok/Twitter/Facebook/Pinterest** = per-platform tabs (posts, stories, history)
- **Settings** = platform connections, app preferences, AI settings

---

## Implementation Order

| # | Phase | Task | Priority | Effort |
|---|-------|------|----------|--------|
| 1 | 1 | App rename + branding | P0 | Small |
| 2 | 1 | DB schema migration (new columns + tables) | P0 | Medium |
| 3 | 1 | Generalize AI analyzer prompt + parser | P0 | Medium |
| 4 | 1 | Remove Fansly + Nova-specific UI | P0 | Small |
| 5 | 1 | Update Photos tab columns | P0 | Medium |
| 6 | 1 | Update Filters tab | P0 | Small |
| 7 | 2 | EXIF extraction on import | P1 | Small |
| 8 | 2 | Albums tab (manual) | P1 | Large |
| 9 | 2 | Duplicate detection | P1 | Medium |
| 10 | 2 | Smart auto-grouping in Gallery | P1 | Medium |
| 11 | 2 | Full-text search | P1 | Small |
| 12 | 2 | Batch file operations | P1 | Medium |
| 13 | 3 | Settings/Connections tab | P0 | Medium |
| 14 | 3 | Instagram Graph API (real) | P0 | Large |
| 15 | 3 | Twitter/X API | P1 | Large |
| 16 | 3 | Multi-platform composer | P0 | Large |
| 17 | 3 | Post scheduler | P1 | Large |
| 18 | 3 | Facebook API | P2 | Large |
| 19 | 3 | Pinterest API | P2 | Large |
| 20 | 4 | Generalized AI scene analysis | P1 | Medium |
| 21 | 4 | Caption generator | P1 | Small |
| 22 | 4 | Hashtag suggestions | P1 | Small |
| 23 | 4 | Image quality scoring | P2 | Medium |

---

## New Dependencies to Add

```
# requirements.txt additions
imagehash>=4.3.1         # Perceptual hash for duplicate detection
watchdog>=4.0.0          # Folder watcher for auto-import
requests-oauthlib>=1.3.1 # OAuth2 flows for social APIs
Pillow[exif]>=10.0.0     # EXIF extraction (Pillow already required)
# Optional: tweepy for Twitter, facebook-sdk for FB
tweepy>=4.14.0           # Twitter/X API v2 client
```

---

## Files to Create

```
core/
  exif_extractor.py       # EXIF reading + normalization
  duplicate_detector.py   # Perceptual + exact hash comparison
  folder_watcher.py       # Watchdog-based auto-import
  social/
    __init__.py
    instagram_api.py      # Graph API implementation
    twitter_api.py        # API v2 implementation
    facebook_api.py       # Graph API (Pages)
    pinterest_api.py      # Pinterest API v5
    threads_api.py        # Threads API
    scheduler.py          # Post scheduler worker thread

ui/
  albums_tab.py           # Albums/Collections UI
  composer_tab.py         # Multi-platform post composer
  schedule_tab.py         # Post queue + calendar
  settings_tab.py         # Platform connections + app prefs
  twitter_tab.py          # Twitter/X UI
  facebook_tab.py         # Facebook UI
  pinterest_tab.py        # Pinterest UI
```

---

## Files to Delete (After Migration)

```
ui/face_matching_tab.py
ui/learning_tab.py
ui/vocabularies_tab.py
core/face_matcher_v2.py
core/face_matcher_deepface.py
```

---

## Risk Log

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Instagram Graph API requires Business account | High | High | Document requirement clearly; fall back to instagrapi as option |
| TikTok API approval gated | Medium | High | Apply for developer access early |
| SQLite schema migration corrupts existing data | Low | High | Backup db before migration; test on copy |
| LLaVA prompt changes break existing workflow | Low | Medium | Version the prompt; keep old prompt as fallback |
| OAuth flow complex in desktop app | Medium | Medium | Use system browser + local redirect server |

---

## Success Metrics

- [ ] App runs without any adult-content-specific UI visible
- [ ] User can import a folder of photos and browse them in under 30 seconds
- [ ] AI tags a photo with scene, mood, objects in under 10 seconds (local LLaVA)
- [ ] User can post to Instagram with a single form + button click
- [ ] User can schedule a post to appear at a future date
- [ ] Duplicate detection finds all exact duplicates in a 1000-photo library
- [ ] Albums support manual drag-and-drop organization

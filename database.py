"""
Database management for Nova Photo Manager
"""
import sqlite3
from datetime import datetime
from pathlib import Path
import json
from cryptography.fernet import Fernet
import base64
import hashlib

class CredentialEncryption:
    """Simple encryption/decryption for API credentials"""
    def __init__(self):
        # Use a machine-specific key derived from the database path
        self.key = self._generate_key()
        self.cipher = Fernet(self.key)
    
    def _generate_key(self):
        """Generate a consistent encryption key based on machine"""
        machine_id = hashlib.sha256(b"nova_photo_manager").hexdigest()[:32]
        key = base64.urlsafe_b64encode(machine_id.encode().ljust(32, b'0')[:32])
        return key
    
    def encrypt(self, data: str) -> str:
        """Encrypt a string"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt a string"""
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception:
            return ""

class PhotoDatabase:
    def __init__(self, db_path="nova_photos.db"):
        """Initialize database connection"""
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.encryption = CredentialEncryption()
        self.connect()
        self.create_tables()
    
    def connect(self):
        """Connect to the database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.ensure_columns()
    
    def ensure_columns(self):
        """Ensure new columns exist in existing databases"""
        try:
            # Check for face_similarity column
            self.cursor.execute("PRAGMA table_info(photos)")
            cols = [row['name'] for row in self.cursor.fetchall()]
            if 'face_similarity' not in cols:
                self.cursor.execute("ALTER TABLE photos ADD COLUMN face_similarity INTEGER DEFAULT 0")
                self.conn.commit()
        except Exception as e:
            print(f"Warning: could not ensure columns: {e}")
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_created TIMESTAMP,
                date_modified TIMESTAMP,
                
                -- AI Analysis fields
                type_of_shot TEXT,
                pose TEXT,
                facing_direction TEXT,
                explicit_level TEXT,
                color_of_clothing TEXT,
                material TEXT,
                type_clothing TEXT,
                footwear TEXT,
                interior_exterior TEXT,
                location TEXT,
                
                -- Workflow status
                status TEXT DEFAULT 'raw',  -- raw, needs_edit, ready, released
                released_instagram BOOLEAN DEFAULT 0,
                released_tiktok BOOLEAN DEFAULT 0,
                released_fansly BOOLEAN DEFAULT 0,
                date_released_instagram TIMESTAMP,
                date_released_tiktok TIMESTAMP,
                date_released_fansly TIMESTAMP,
                
                -- Additional metadata
                package_name TEXT,
                notes TEXT,
                tags TEXT,
                
                -- Face similarity (1-5 rating)
                face_similarity INTEGER DEFAULT 0
            )
        ''')

        # New: photo_packages for multi-package support
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS photo_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER NOT NULL,
                package_name TEXT NOT NULL,
                FOREIGN KEY (photo_id) REFERENCES photos(id)
            )
        ''')
        
        # Create AI corrections tracking table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER,
                field_name TEXT NOT NULL,
                original_value TEXT,
                corrected_value TEXT,
                correction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (photo_id) REFERENCES photos(id)
            )
        ''')
        
        # Create controlled vocabulary table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS vocabularies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                field_name TEXT NOT NULL,
                value TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER DEFAULT 0,
                UNIQUE(field_name, value)
            )
        ''')
        
        # Credentials table for API tokens (encrypted)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL UNIQUE,
                encrypted_data TEXT NOT NULL,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Posting history table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS posting_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                post_type TEXT,
                caption TEXT,
                post_url TEXT,
                post_id TEXT,
                date_posted TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'success',
                error_message TEXT,
                FOREIGN KEY (photo_id) REFERENCES photos(id)
            )
        ''')
        
        self.conn.commit()
        self.migrate_schema()
        self.migrate_vocabulary_descriptions()
        self.init_vocabularies()

        # Ensure photo_packages table exists in older DBs
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS photo_packages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    photo_id INTEGER NOT NULL,
                    package_name TEXT NOT NULL,
                    FOREIGN KEY (photo_id) REFERENCES photos(id)
                )
            ''')
            self.conn.commit()
        except Exception:
            pass
    
    def add_photo(self, filepath, metadata=None):
        """Add a photo to the database"""
        filepath = str(Path(filepath).resolve())
        filename = Path(filepath).name
        
        # Get file creation time
        try:
            date_created = datetime.fromtimestamp(Path(filepath).stat().st_ctime)
        except:
            date_created = None
        
        try:
            self.cursor.execute('''
                INSERT INTO photos (filepath, filename, date_created)
                VALUES (?, ?, ?)
            ''', (filepath, filename, date_created))
            
            photo_id = self.cursor.lastrowid
            
            # Update metadata if provided
            if metadata:
                self.update_photo_metadata(photo_id, metadata)
                # If metadata contains package_name, sync into photo_packages
                pkg = metadata.get('package_name') if isinstance(metadata, dict) else None
                if pkg:
                    self.set_packages(photo_id, [pkg])
            
            self.conn.commit()
            return photo_id
        except sqlite3.IntegrityError:
            # Photo already exists, return existing ID
            self.cursor.execute('SELECT id FROM photos WHERE filepath = ?', (filepath,))
            return self.cursor.fetchone()[0]
    
    def update_photo_metadata(self, photo_id, metadata):
        """Update photo metadata"""
        fields = []
        values = []
        
        for key, value in metadata.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        if fields:
            values.append(photo_id)
            query = f"UPDATE photos SET {', '.join(fields)} WHERE id = ?"
            self.cursor.execute(query, values)
            self.conn.commit()

    # --- Package helpers ---
    def get_packages(self, photo_id):
        """Return list of package names for a photo"""
        self.cursor.execute('SELECT package_name FROM photo_packages WHERE photo_id = ? ORDER BY id', (photo_id,))
        return [row[0] for row in self.cursor.fetchall()]

    def set_packages(self, photo_id, packages):
        """Replace packages for a photo; also sync photos.package_name with the first package for compatibility"""
        # Clean list
        clean = [p.strip() for p in packages if p and p.strip()]
        self.cursor.execute('DELETE FROM photo_packages WHERE photo_id = ?', (photo_id,))
        for pkg in clean:
            self.cursor.execute('INSERT INTO photo_packages (photo_id, package_name) VALUES (?, ?)', (photo_id, pkg))
        # Keep legacy column in sync with first package
        legacy = clean[0] if clean else ''
        self.cursor.execute('UPDATE photos SET package_name = ? WHERE id = ?', (legacy, photo_id))
        self.conn.commit()

    def add_package(self, photo_id, package_name):
        """Add a single package to a photo if not present"""
        pkg = (package_name or '').strip()
        if not pkg:
            return
        existing = set(self.get_packages(photo_id))
        if pkg in existing:
            return
        self.cursor.execute('INSERT INTO photo_packages (photo_id, package_name) VALUES (?, ?)', (photo_id, pkg))
        if not existing:
            self.cursor.execute('UPDATE photos SET package_name = ? WHERE id = ?', (pkg, photo_id))
        self.conn.commit()

    def clear_packages(self, photo_id):
        """Remove all packages from a photo and clear legacy column"""
        self.cursor.execute('DELETE FROM photo_packages WHERE photo_id = ?', (photo_id,))
        self.cursor.execute('UPDATE photos SET package_name = "" WHERE id = ?', (photo_id,))
        self.conn.commit()
    
    def get_photo(self, photo_id):
        """Get photo by ID"""
        self.cursor.execute('SELECT * FROM photos WHERE id = ?', (photo_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def get_photo_by_path(self, filepath):
        """Get photo by filepath"""
        filepath = str(Path(filepath).resolve())
        self.cursor.execute('SELECT * FROM photos WHERE filepath = ?', (filepath,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_photos(self, filters=None):
        """Get all photos with optional filters"""
        query = 'SELECT * FROM photos WHERE 1=1'
        params = []
        
        if filters:
            if filters.get('needs_editing'):
                query += ' AND needs_editing = 1'
            if filters.get('ready'):
                query += ' AND ready = 1'
            if filters.get('released_instagram'):
                query += ' AND released_instagram = 1'
            if filters.get('released_tiktok'):
                query += ' AND released_tiktok = 1'
            if filters.get('released_fansly'):
                query += ' AND released_fansly = 1'
            if filters.get('package_name'):
                query += ' AND package_name = ?'
                params.append(filters['package_name'])
        
        query += ' ORDER BY date_added DESC'
        
        self.cursor.execute(query, params)
        return [dict(row) for row in self.cursor.fetchall()]
    
    def bulk_update(self, photo_ids, updates):
        """Bulk update multiple photos"""
        for photo_id in photo_ids:
            self.update_photo_metadata(photo_id, updates)
    
    def delete_photo(self, photo_id):
        """Delete a photo from database"""
        self.cursor.execute('DELETE FROM photos WHERE id = ?', (photo_id,))
        self.conn.commit()
    
    def add_tag_to_photo(self, photo_id, tag):
        """Add a tag to a photo"""
        photo = self.get_photo(photo_id)
        if not photo:
            return
        
        tags = self.get_photo_tags(photo_id)
        tag = tag.strip().lower()
        
        if tag and tag not in tags:
            tags.append(tag)
            self.update_photo_metadata(photo_id, {'tags': ','.join(tags)})
    
    def remove_tag_from_photo(self, photo_id, tag):
        """Remove a tag from a photo"""
        tags = self.get_photo_tags(photo_id)
        tag = tag.strip().lower()
        
        if tag in tags:
            tags.remove(tag)
            self.update_photo_metadata(photo_id, {'tags': ','.join(tags)})
    
    def get_photo_tags(self, photo_id):
        """Get list of tags for a photo"""
        photo = self.get_photo(photo_id)
        if not photo or not photo.get('tags'):
            return []
        return [tag.strip() for tag in photo['tags'].split(',') if tag.strip()]
    
    def set_photo_tags(self, photo_id, tags_list):
        """Set tags for a photo (replaces existing tags)"""
        # Clean and normalize tags
        cleaned_tags = [tag.strip().lower() for tag in tags_list if tag.strip()]
        self.update_photo_metadata(photo_id, {'tags': ','.join(cleaned_tags)})
    
    def get_all_tags(self):
        """Get all unique tags with their counts"""
        self.cursor.execute('SELECT tags FROM photos WHERE tags IS NOT NULL AND tags != ""')
        tag_count = {}
        
        for row in self.cursor.fetchall():
            if row['tags']:
                tags = [tag.strip().lower() for tag in row['tags'].split(',') if tag.strip()]
                for tag in tags:
                    tag_count[tag] = tag_count.get(tag, 0) + 1
        
        # Return sorted by count descending
        return sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
    
    def get_photos_by_tag(self, tag):
        """Get all photos with a specific tag"""
        tag = tag.strip().lower()
        self.cursor.execute('SELECT * FROM photos WHERE tags LIKE ?', (f'%{tag}%',))
        photos = []
        
        for row in self.cursor.fetchall():
            photo = dict(row)
            # Verify tag actually matches (not just substring)
            photo_tags = [t.strip().lower() for t in (photo.get('tags') or '').split(',')]
            if tag in photo_tags:
                photos.append(photo)
        
        return photos
    
    def migrate_schema(self):
        """Migrate old schema to new status column"""
        try:
            # Check if old columns exist
            self.cursor.execute("PRAGMA table_info(photos)")
            columns = {row[1] for row in self.cursor.fetchall()}
            
            if 'needs_editing' in columns or 'ready' in columns:
                # Add status column if it doesn't exist
                if 'status' not in columns:
                    self.cursor.execute('ALTER TABLE photos ADD COLUMN status TEXT DEFAULT "raw"')
                
                # Migrate data from old columns
                if 'needs_editing' in columns and 'ready' in columns:
                    self.cursor.execute('''
                        UPDATE photos SET status = 
                            CASE 
                                WHEN ready = 1 THEN 'ready'
                                WHEN needs_editing = 1 THEN 'needs_edit'
                                ELSE 'raw'
                            END
                        WHERE status IS NULL OR status = 'raw'
                    ''')
                    self.conn.commit()
        except Exception as e:
            print(f"Migration warning: {e}")
    
    def migrate_vocabulary_descriptions(self):
        """Add description column to vocabularies table if it doesn't exist"""
        try:
            self.cursor.execute("PRAGMA table_info(vocabularies)")
            columns = {row[1] for row in self.cursor.fetchall()}
            
            if 'description' not in columns:
                print("Migrating vocabularies table to add description column...")
                self.cursor.execute('ALTER TABLE vocabularies ADD COLUMN description TEXT')
                self.conn.commit()
                print("Migration complete")
        except Exception as e:
            print(f"Vocabulary migration warning: {e}")
    
    def save_correction(self, photo_id, field, original_value, corrected_value):
        """Save a user correction for AI learning"""
        self.cursor.execute('''
            INSERT INTO ai_corrections (photo_id, field_name, original_value, corrected_value, correction_date)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (photo_id, field, original_value, corrected_value))
        self.conn.commit()
    
    def get_corrections_for_field(self, field, limit=10):
        """Get recent corrections for a specific field to use as examples"""
        self.cursor.execute('''
            SELECT original_value, corrected_value, COUNT(*) as frequency
            FROM ai_corrections
            WHERE field_name = ?
            GROUP BY original_value, corrected_value
            ORDER BY correction_date DESC
            LIMIT ?
        ''', (field, limit))
        return self.cursor.fetchall()
    
    def get_all_corrections_summary(self):
        """Get summary of all corrections for analysis"""
        self.cursor.execute('''
            SELECT field_name, COUNT(*) as correction_count
            FROM ai_corrections
            GROUP BY field_name
            ORDER BY correction_count DESC
        ''')
        return self.cursor.fetchall()
    
    def get_corrected_fields_for_photo(self, photo_id):
        """Get list of fields that have been manually corrected for a specific photo"""
        self.cursor.execute('''
            SELECT DISTINCT field_name
            FROM ai_corrections
            WHERE photo_id = ?
        ''', (photo_id,))
        return [row[0] for row in self.cursor.fetchall()]
    
    def init_vocabularies(self):
        """Initialize vocabularies with default values if empty"""
        # Check if vocabularies already exist
        self.cursor.execute('SELECT COUNT(*) FROM vocabularies')
        if self.cursor.fetchone()[0] > 0:
            return  # Already initialized
        
        # Default vocabularies for each field
        default_vocabs = {
            'type_of_shot': ['selfie', 'portrait', 'fullbody', 'closeup'],
            'pose': ['standing', 'sitting', 'lying', 'kneeling', 'leaning'],
            'facing_direction': ['camera', 'away', 'up', 'down', 'left', 'right'],
            'explicit_level': ['sfw', 'mild', 'suggestive', 'explicit'],
            'color_of_clothing': ['white', 'beige', 'cream', 'pink', 'black', 'blue', 'red', 'green', 'nude'],
            'material': ['sheer', 'satin', 'lace', 'cotton', 'silk', 'leather', 'none'],
            'type_clothing': ['robe', 'tanktop', 'tshirt', 'dress', 'bikini', 'lingerie', 'pants', 'shorts', 'skirt', 'nude'],
            'footwear': ['barefoot', 'shoes', 'socks', 'heels', 'boots', 'sandals', 'hose', 'stockings'],
            'interior_exterior': ['interior', 'exterior'],
            'location': ['bed', 'beach', 'bath', 'restaurant', 'office', 'desk', 'couch', 'chair', 'kitchen', 'bedroom', 'bathroom']
        }
        
        for field, values in default_vocabs.items():
            for i, value in enumerate(values):
                self.cursor.execute(
                    'INSERT OR IGNORE INTO vocabularies (field_name, value, sort_order) VALUES (?, ?, ?)',
                    (field, value, i)
                )
        
        self.conn.commit()
    
    def get_vocabulary(self, field_name, include_descriptions=False):
        """Get all allowed values for a field"""
        if include_descriptions:
            self.cursor.execute(
                'SELECT value, description FROM vocabularies WHERE field_name = ? ORDER BY sort_order, value',
                (field_name,)
            )
            return [(row[0], row[1]) for row in self.cursor.fetchall()]
        else:
            self.cursor.execute(
                'SELECT value FROM vocabularies WHERE field_name = ? ORDER BY sort_order, value',
                (field_name,)
            )
            return [row[0] for row in self.cursor.fetchall()]
    
    def add_vocabulary_value(self, field_name, value, description=None):
        """Add a new value to field vocabulary"""
        value = value.strip().lower()
        if not value:
            return False
        try:
            self.cursor.execute(
                'INSERT OR IGNORE INTO vocabularies (field_name, value, description) VALUES (?, ?, ?)',
                (field_name, value, description)
            )
            self.conn.commit()
            return True
        except:
            return False
    
    def update_vocabulary_description(self, field_name, value, description):
        """Update description for a vocabulary value"""
        try:
            self.cursor.execute(
                'UPDATE vocabularies SET description = ? WHERE field_name = ? AND value = ?',
                (description, field_name, value)
            )
            self.conn.commit()
            return True
        except:
            return False
    
    def remove_vocabulary_value(self, field_name, value):
        """Remove a value from field vocabulary"""
        self.cursor.execute(
            'DELETE FROM vocabularies WHERE field_name = ? AND value = ?',
            (field_name, value)
        )
        self.conn.commit()
    
    def rename_vocabulary_value(self, field_name, old_value, new_value):
        """Rename a vocabulary value and update all photos using it"""
        new_value = new_value.strip().lower()
        if not new_value:
            return False
        
        try:
            # Update the vocabulary
            self.cursor.execute(
                'UPDATE vocabularies SET value = ? WHERE field_name = ? AND value = ?',
                (new_value, field_name, old_value)
            )
            
            # Update all photos using this value
            self.cursor.execute(
                f'UPDATE photos SET {field_name} = ? WHERE {field_name} = ?',
                (new_value, old_value)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error renaming vocabulary: {e}")
            return False
    
    def store_api_credentials(self, platform: str, credentials: dict):
        """Store encrypted API credentials for a platform (instagram, tiktok, etc.)"""
        try:
            encrypted_data = self.encryption.encrypt(json.dumps(credentials))
            self.cursor.execute('''
                INSERT OR REPLACE INTO api_credentials (platform, encrypted_data, date_modified)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (platform.lower(), encrypted_data))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error storing credentials: {e}")
            return False
    
    def get_api_credentials(self, platform: str) -> dict:
        """Retrieve decrypted API credentials for a platform"""
        try:
            self.cursor.execute('''
                SELECT encrypted_data FROM api_credentials WHERE platform = ?
            ''', (platform.lower(),))
            row = self.cursor.fetchone()
            if row:
                decrypted = self.encryption.decrypt(row['encrypted_data'])
                return json.loads(decrypted) if decrypted else {}
        except Exception as e:
            print(f"Error retrieving credentials: {e}")
        return {}
    
    def delete_api_credentials(self, platform: str):
        """Delete API credentials for a platform"""
        try:
            self.cursor.execute('DELETE FROM api_credentials WHERE platform = ?', (platform.lower(),))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting credentials: {e}")
            return False
    
    def has_api_credentials(self, platform: str) -> bool:
        """Check if credentials exist for a platform"""
        try:
            self.cursor.execute('SELECT 1 FROM api_credentials WHERE platform = ?', (platform.lower(),))
            return self.cursor.fetchone() is not None
        except Exception:
            return False
    
    def log_post(self, photo_id: int, platform: str, post_type: str, caption: str, 
                 post_url: str = None, post_id: str = None, status: str = 'success', error_msg: str = None):
        """Log a post to the posting history"""
        try:
            self.cursor.execute('''
                INSERT INTO posting_history 
                (photo_id, platform, post_type, caption, post_url, post_id, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (photo_id, platform.lower(), post_type, caption, post_url, post_id, status, error_msg))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error logging post: {e}")
            return False
    
    def get_posting_history(self, photo_id: int = None, platform: str = None, limit: int = 100) -> list:
        """Get posting history, optionally filtered"""
        try:
            query = 'SELECT * FROM posting_history WHERE 1=1'
            params = []
            if photo_id:
                query += ' AND photo_id = ?'
                params.append(photo_id)
            if platform:
                query += ' AND platform = ?'
                params.append(platform.lower())
            query += ' ORDER BY date_posted DESC LIMIT ?'
            params.append(limit)
            
            self.cursor.execute(query, params)
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Error retrieving posting history: {e}")
            return []
            
            self.conn.commit()
            return True
        except:
            return False
    
    def cleanup_unused_vocabulary(self, field_name):
        """Remove vocabulary values that are not used by any photo"""
        # Get all values in vocabulary
        vocab = self.get_vocabulary(field_name)
        
        for value in vocab:
            # Check if any photo uses this value
            self.cursor.execute(
                f'SELECT COUNT(*) FROM photos WHERE {field_name} = ?',
                (value,)
            )
            count = self.cursor.fetchone()[0]
            
            if count == 0:
                # Not used, remove it
                self.remove_vocabulary_value(field_name, value)
    
    def validate_and_constrain(self, field_name, value):
        """Validate a value against vocabulary, return 'unknown' if not found"""
        if not value:
            return 'unknown'
        
        value = value.strip().lower()
        vocab = self.get_vocabulary(field_name)
        
        if value in vocab:
            return value
        else:
            return 'unknown'
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

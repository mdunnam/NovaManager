"""Test script to verify tag storage"""
from database import PhotoDatabase

db = PhotoDatabase("H:\\NovaApp\\nova_photos.db")

# Get first photo
photos = db.get_all_photos()
if photos:
    photo = photos[0]
    photo_id = photo['id']
    
    # Set many tags
    test_tags = "tag1, tag2, tag3, tag4, tag5, tag6, tag7, tag8, tag9, tag10"
    print(f"Setting tags for photo {photo_id}: {test_tags}")
    db.update_photo_metadata(photo_id, {'tags': test_tags})
    
    # Read back
    updated_photo = db.get_photo(photo_id)
    print(f"Tags stored in database: {updated_photo['tags']}")
    print(f"Tag count: {len(updated_photo['tags'].split(','))}")
    
    # Get all tags
    all_tags = db.get_all_tags()
    print(f"\nAll tags in database: {all_tags}")
else:
    print("No photos in database")

db.close()

"""
Post scheduler background worker for PhotoFlow.
Checks the scheduled_posts table and fires posts when their time comes.
"""
from datetime import datetime

try:
    from PyQt6.QtCore import QThread, pyqtSignal
    _QT = True
except ImportError:
    _QT = False

from core.database import PhotoDatabase


def _get_api(platform: str, credentials: dict):
    """Return the appropriate API instance for a platform."""
    p = platform.lower()
    if p == 'instagram':
        from core.social.instagram_api import InstagramAPI
        return InstagramAPI(credentials)
    if p in ('twitter', 'x'):
        from core.social.twitter_api import TwitterAPI
        return TwitterAPI(credentials)
    return None


if _QT:
    class SchedulerWorker(QThread):
        """
        Background thread that polls for scheduled posts every 60 seconds
        and fires them when due.
        """
        post_sent = pyqtSignal(dict)    # scheduled_post row
        post_failed = pyqtSignal(dict, str)  # row, error message
        tick = pyqtSignal()

        def __init__(self, db_path: str, credentials_getter, interval_secs: int = 60):
            super().__init__()
            self.db_path = db_path
            self.credentials_getter = credentials_getter  # callable(platform) -> dict
            self.interval_secs = interval_secs
            self._running = True

        def run(self):
            import time
            while self._running:
                self.tick.emit()
                try:
                    self._process_due_posts()
                except Exception as e:
                    print(f'[Scheduler] Error: {e}')
                # Sleep in small increments so stop() is responsive
                for _ in range(self.interval_secs * 10):
                    if not self._running:
                        break
                    time.sleep(0.1)

        def _process_due_posts(self):
            db = PhotoDatabase(self.db_path)
            try:
                now = datetime.utcnow().isoformat()
                pending = [
                    p for p in db.get_scheduled_posts()
                    if p.get('status') == 'pending'
                    and p.get('scheduled_time', '') <= now
                ]
                for post in pending:
                    self._fire_post(db, post)
            finally:
                db.close()

        def _fire_post(self, db, post: dict):
            platform = post.get('platform', '')
            photo = db.get_photo(post['photo_id']) if post.get('photo_id') else None
            if not photo:
                db.update_scheduled_post_status(post['id'], 'failed')
                self.post_failed.emit(post, 'Photo not found')
                return

            try:
                creds = self.credentials_getter(platform)
                api = _get_api(platform, creds)
                if not api:
                    raise ValueError(f'Unknown platform: {platform}')

                result = api.post_photo(
                    photo.get('filepath', ''),
                    caption=post.get('caption', ''),
                    hashtags=(post.get('hashtags') or '').split(','),
                )

                if result.success:
                    db.update_scheduled_post_status(post['id'], 'sent',
                                                    post_url=result.url,
                                                    post_id_str=result.post_id)
                    self.post_sent.emit(post)
                else:
                    db.update_scheduled_post_status(post['id'], 'failed',
                                                    error_msg=result.error)
                    self.post_failed.emit(post, result.error)

            except Exception as e:
                db.update_scheduled_post_status(post['id'], 'failed', error_msg=str(e))
                self.post_failed.emit(post, str(e))

        def stop(self):
            self._running = False

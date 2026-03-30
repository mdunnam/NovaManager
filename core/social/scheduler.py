"""Post scheduler background worker for PhotoFlow.

Polls the scheduled_posts table, posts anything due, and retries failures with
an exponential backoff until max_retries is reached.
"""
from datetime import datetime, timedelta

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
    if p == 'facebook':
        from core.social.facebook_api import FacebookAPI
        return FacebookAPI(credentials)
    if p == 'pinterest':
        from core.social.pinterest_api import PinterestAPI
        return PinterestAPI(credentials)
    if p == 'threads':
        from core.social.threads_api import ThreadsAPI
        return ThreadsAPI(credentials)
    if p == 'tiktok':
        from core.social.tiktok_api import TikTokAPI
        return TikTokAPI(credentials)
    return None


def _parse_timestamp(value: str | None):
    """Best-effort conversion of a DB timestamp string to a datetime."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', ''))
    except ValueError:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _retry_backoff_seconds(attempt_number: int) -> int:
    """Return the backoff delay for the given retry attempt number."""
    return min(3600, 60 * (2 ** max(0, attempt_number - 1)))


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
                now = datetime.utcnow()
                due_posts = []
                for post in db.get_scheduled_posts():
                    status = (post.get('status') or '').lower()
                    scheduled_at = _parse_timestamp(post.get('scheduled_time'))
                    next_retry_at = _parse_timestamp(post.get('next_retry_at'))
                    retry_count = int(post.get('retry_count') or 0)
                    max_retries = int(post.get('max_retries') or 3)

                    if status == 'pending' and scheduled_at and scheduled_at <= now:
                        due_posts.append(post)
                    elif (
                        status == 'failed'
                        and retry_count < max_retries
                        and next_retry_at
                        and next_retry_at <= now
                    ):
                        due_posts.append(post)

                for post in due_posts:
                    self._fire_post(db, post)
            finally:
                db.close()

        def _fire_post(self, db, post: dict):
            now = datetime.utcnow()
            attempt_number = int(post.get('retry_count') or 0) + 1
            db.update_scheduled_post_status(
                post['id'],
                'sending',
                error_msg='',
                retry_count=attempt_number,
                last_attempt_at=now.isoformat(),
                next_retry_at='',
            )

            platform = post.get('platform', '')
            photo = db.get_photo(post['photo_id']) if post.get('photo_id') else None
            if not photo:
                msg = 'Photo not found'
                db.update_scheduled_post_status(
                    post['id'],
                    'failed',
                    error_msg=msg,
                    retry_count=attempt_number,
                    last_attempt_at=now.isoformat(),
                    next_retry_at='',
                )
                self.post_failed.emit(post, msg)
                return

            try:
                creds = self.credentials_getter(platform)
                api = _get_api(platform, creds)
                if not api:
                    raise ValueError(f'Unknown platform: {platform}')

                result = api.post_photo(
                    photo.get('filepath', ''),
                    caption=post.get('caption', ''),
                    hashtags=(post.get('hashtags') or '').replace(',', ' ').split(),
                    alt_text=photo.get('alt_text', '') or '',
                )

                if result.success:
                    db.update_scheduled_post_status(
                        post['id'],
                        'sent',
                        post_url=result.url,
                        post_id_str=result.post_id,
                        error_msg='',
                        retry_count=attempt_number,
                        last_attempt_at=now.isoformat(),
                        next_retry_at='',
                    )
                    db.log_post(
                        photo_id=photo['id'],
                        platform=platform,
                        post_type=post.get('post_type', 'post'),
                        caption=post.get('caption', ''),
                        post_url=result.url,
                        post_id=result.post_id,
                        status='success',
                    )
                    self.post_sent.emit(post)
                else:
                    max_retries = int(post.get('max_retries') or 3)
                    next_retry_at = ''
                    message = result.error or 'Unknown posting failure'
                    if attempt_number < max_retries:
                        retry_in = _retry_backoff_seconds(attempt_number)
                        next_retry_at = (now + timedelta(seconds=retry_in)).isoformat()
                        message = f'{message} Retrying in {retry_in}s.'
                    db.update_scheduled_post_status(
                        post['id'],
                        'failed',
                        error_msg=message,
                        retry_count=attempt_number,
                        last_attempt_at=now.isoformat(),
                        next_retry_at=next_retry_at,
                    )
                    self.post_failed.emit(post, message)

            except Exception as e:
                message = str(e)
                max_retries = int(post.get('max_retries') or 3)
                next_retry_at = ''
                if attempt_number < max_retries:
                    retry_in = _retry_backoff_seconds(attempt_number)
                    next_retry_at = (now + timedelta(seconds=retry_in)).isoformat()
                    message = f'{message} Retrying in {retry_in}s.'
                db.update_scheduled_post_status(
                    post['id'],
                    'failed',
                    error_msg=message,
                    retry_count=attempt_number,
                    last_attempt_at=now.isoformat(),
                    next_retry_at=next_retry_at,
                )
                self.post_failed.emit(post, message)

        def stop(self):
            self._running = False

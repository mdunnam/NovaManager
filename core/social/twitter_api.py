"""
Twitter/X API v2 integration for PhotoFlow.

Required credentials:
  api_key            — Consumer API key
  api_secret         — Consumer API secret
  access_token       — OAuth 1.0a access token
  access_token_secret — OAuth 1.0a access token secret

Media uploads use v1.1 endpoint; tweets use v2.
"""
import os

try:
    import requests as _requests
    from requests_oauthlib import OAuth1
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

from .base import SocialPlatform, PostResult

_UPLOAD_URL = 'https://upload.twitter.com/1.1/media/upload.json'
_TWEET_URL = 'https://api.twitter.com/2/tweets'


class TwitterAPI(SocialPlatform):
    platform_name = 'twitter'

    def is_connected(self) -> bool:
        return all(self.credentials.get(k) for k in (
            'api_key', 'api_secret', 'access_token', 'access_token_secret'
        ))

    def _auth(self):
        """Build OAuth1 auth object."""
        return OAuth1(
            self.credentials['api_key'],
            self.credentials['api_secret'],
            self.credentials['access_token'],
            self.credentials['access_token_secret'],
        )

    def verify_credentials(self) -> tuple[bool, str]:
        if not self.is_connected():
            return False, 'Missing Twitter API credentials'
        if not _HAS_REQUESTS:
            return False, 'requests / requests-oauthlib not installed'
        try:
            r = _requests.get(
                'https://api.twitter.com/1.1/account/verify_credentials.json',
                auth=self._auth(),
                timeout=10
            )
            data = r.json()
            if r.status_code == 200:
                return True, f"Connected as @{data.get('screen_name', '?')}"
            return False, data.get('errors', [{}])[0].get('message', 'Auth failed')
        except Exception as e:
            return False, str(e)

    def _upload_media(self, filepath: str) -> str | None:
        """Upload media file and return media_id_string, or None on error."""
        try:
            with open(filepath, 'rb') as f:
                r = _requests.post(
                    _UPLOAD_URL,
                    files={'media': f},
                    auth=self._auth(),
                    timeout=60
                )
            data = r.json()
            return data.get('media_id_string')
        except Exception:
            return None

    def post_photo(self, filepath: str, caption: str = '',
                   hashtags: list[str] | None = None) -> PostResult:
        if not _HAS_REQUESTS:
            return PostResult(False, self.platform_name, error='requests not installed')
        if not self.is_connected():
            return PostResult(False, self.platform_name, error='Not connected')

        full_caption = self._build_caption(caption, hashtags)

        # Upload media (only for local files)
        media_id = None
        if filepath and not filepath.startswith('http') and os.path.exists(filepath):
            media_id = self._upload_media(filepath)
            if not media_id:
                return PostResult(False, self.platform_name, error='Media upload failed')

        # Post tweet
        try:
            payload = {'text': full_caption[:280]}
            if media_id:
                payload['media'] = {'media_ids': [media_id]}

            r = _requests.post(
                _TWEET_URL,
                json=payload,
                auth=self._auth(),
                timeout=30
            )
            data = r.json()
            if r.status_code in (200, 201):
                tweet = data.get('data', {})
                post_id = tweet.get('id', '')
                url = f'https://twitter.com/i/web/status/{post_id}' if post_id else ''
                return PostResult(True, self.platform_name, post_id=post_id, url=url)
            errors = data.get('errors', [{}])
            msg = errors[0].get('message', f'HTTP {r.status_code}') if errors else f'HTTP {r.status_code}'
            return PostResult(False, self.platform_name, error=msg)
        except Exception as e:
            return PostResult(False, self.platform_name, error=str(e))

    def get_auth_url(self) -> str:
        """Return link to developer portal for manual token setup."""
        return 'https://developer.twitter.com/en/portal/dashboard'

"""
TikTok platform integration.

TikTok does not provide a public Content Posting API for third-party apps
without an approved Content Posting API partner agreement.  This module
provides the interface expected by the rest of the codebase and will surface
a clear error rather than silently failing.
"""
from core.social.base import SocialPlatform, PostResult


class TikTokAPI(SocialPlatform):
    """TikTok integration stub.

    The TikTok Content Posting API requires a partner agreement that most
    independent apps do not have.  Methods return a descriptive failure result
    rather than raising unhandled exceptions.
    """

    platform_name = 'tiktok'

    _NOT_AVAILABLE_MSG = (
        'Direct TikTok posting is not available without an approved TikTok '
        'Content Posting API partner agreement.  Use the TikTok mobile app '
        'or Creator Portal to publish content manually.'
    )

    def is_connected(self) -> bool:
        """Return True only if an access_token credential is present."""
        return bool(self.credentials.get('access_token'))

    def post_photo(
        self,
        filepath: str,
        caption: str = '',
        hashtags: list | None = None,
        alt_text: str = '',
    ) -> PostResult:
        """Attempt to post a photo/video to TikTok.

        Args:
            filepath: Absolute path to the media file.
            caption: Post caption text.
            hashtags: Optional list of hashtag strings.

        Returns:
            PostResult with success=False and an informative error message
            unless a real access_token is configured, in which case the
            upload is attempted via the TikTok API.
        """
        if not self.is_connected():
            return PostResult(
                success=False,
                platform=self.platform_name,
                error=self._NOT_AVAILABLE_MSG,
            )

        try:
            import requests
            from pathlib import Path

            token = self.credentials['access_token']
            full_caption = self._build_caption(caption, hashtags)

            # Step 1: initialise upload
            init_resp = requests.post(
                'https://open.tiktokapis.com/v2/post/publish/video/init/',
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json; charset=UTF-8',
                },
                json={
                    'post_info': {
                        'title': full_caption[:150],
                        'privacy_level': 'SELF_ONLY',  # safer default
                        'disable_duet': False,
                        'disable_comment': False,
                        'disable_stitch': False,
                    },
                    'source_info': {
                        'source': 'FILE_UPLOAD',
                        'video_size': Path(filepath).stat().st_size,
                        'chunk_size': Path(filepath).stat().st_size,
                        'total_chunk_count': 1,
                    },
                },
                timeout=30,
            )
            init_resp.raise_for_status()
            init_data = init_resp.json()

            publish_id = init_data.get('data', {}).get('publish_id', '')
            upload_url = init_data.get('data', {}).get('upload_url', '')

            if not upload_url:
                return PostResult(
                    success=False,
                    platform=self.platform_name,
                    error=f'TikTok did not return an upload URL: {init_data}',
                )

            # Step 2: upload the file
            file_size = Path(filepath).stat().st_size
            with open(filepath, 'rb') as f:
                upload_resp = requests.put(
                    upload_url,
                    headers={
                        'Content-Range': f'bytes 0-{file_size - 1}/{file_size}',
                        'Content-Length': str(file_size),
                        'Content-Type': 'video/mp4',
                    },
                    data=f,
                    timeout=120,
                )
            upload_resp.raise_for_status()

            return PostResult(
                success=True,
                platform=self.platform_name,
                post_id=publish_id,
            )

        except Exception as exc:
            return PostResult(
                success=False,
                platform=self.platform_name,
                error=str(exc),
            )

    def verify_credentials(self) -> tuple[bool, str]:
        """Verify TikTok credentials by calling the user-info endpoint."""
        if not self.is_connected():
            return False, self._NOT_AVAILABLE_MSG

        try:
            import requests
            token = self.credentials['access_token']
            resp = requests.get(
                'https://open.tiktokapis.com/v2/user/info/',
                headers={'Authorization': f'Bearer {token}'},
                params={'fields': 'open_id,union_id,display_name'},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json().get('data', {}).get('user', {})
                name = data.get('display_name', 'unknown')
                return True, f'Connected as {name}'
            return False, f'TikTok API error {resp.status_code}: {resp.text}'
        except Exception as exc:
            return False, str(exc)

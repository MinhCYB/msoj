import hashlib
import logging
import os
import secrets
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings

__all__ = ['PolygonAPIError', 'PolygonClient']

logger = logging.getLogger('judge.polygon')

API_URL = 'https://polygon.codeforces.com/api/'
ZIP_MAGIC = b'PK'
MAX_INTERVAL = 12.0


class PolygonAPIError(Exception):
    pass


class PolygonClient:
    """
    Minimal Polygon API client.

    Polygon sits behind a rate limiter that answers 429 when requests arrive faster than roughly one every
    couple of seconds, so every request is spaced by `min_interval` and 429/5xx responses are retried with
    a growing delay.
    """

    def __init__(self, key: Optional[str] = None, secret: Optional[str] = None,
                 min_interval: Optional[float] = None, max_retries: int = 6):
        self.key = key or os.environ.get('POLYGON_API_KEY')
        self.secret = secret or os.environ.get('POLYGON_API_SECRET')
        if not self.key or not self.secret:
            raise PolygonAPIError('POLYGON_API_KEY and POLYGON_API_SECRET must be set in the environment')
        self.min_interval = settings.POLYGON_API_MIN_INTERVAL if min_interval is None else min_interval
        self.max_retries = max_retries
        self.session = requests.Session()
        self._lock = threading.Lock()
        self._last_request = 0.0

    def _throttle(self):
        with self._lock:
            wait = self._last_request + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    def _signed(self, method: str, params: Dict[str, Any]) -> Dict[str, str]:
        params = {k: str(v) for k, v in params.items() if v is not None}
        params['apiKey'] = self.key
        params['time'] = str(int(time.time()))
        query = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
        rand = secrets.token_hex(3)
        digest = hashlib.sha512(f'{rand}/{method}?{query}#{self.secret}'.encode()).hexdigest()
        params['apiSig'] = rand + digest
        return params

    def _post(self, method: str, params: Dict[str, Any], stream: bool = False) -> requests.Response:
        last_error = 'no response'
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                response = self.session.post(API_URL + method, data=self._signed(method, params),
                                             timeout=(15, 300), stream=stream)
            except requests.RequestException as e:
                last_error = type(e).__name__
            else:
                if response.status_code != 429 and response.status_code < 500:
                    return response
                last_error = f'HTTP {response.status_code}'
                if response.status_code == 429:
                    # The limiter is stricter than the configured spacing: slow down for the rest of the run.
                    self.min_interval = min(max(self.min_interval, 1.0) * 1.5, MAX_INTERVAL)
                response.close()
            delay = self.min_interval * (2 ** attempt)
            logger.warning('Polygon %s failed (%s), retry %d in %.0fs', method, last_error, attempt + 1, delay)
            time.sleep(delay)
        raise PolygonAPIError(f'{method} failed after {self.max_retries} attempts ({last_error})')

    def call(self, method: str, **params) -> Any:
        response = self._post(method, params)
        try:
            data = response.json()
        except ValueError:
            raise PolygonAPIError(f'{method} returned HTTP {response.status_code} without JSON')
        if data.get('status') != 'OK':
            raise PolygonAPIError(f'{method}: {data.get("comment", "unknown error")}')
        return data.get('result')

    def list_problems(self) -> List[dict]:
        return self.call('problems.list')

    def view_tags(self, problem_id: int) -> List[str]:
        return self.call('problem.viewTags', problemId=problem_id) or []

    def packages(self, problem_id: int) -> List[dict]:
        return self.call('problem.packages', problemId=problem_id)

    def download_package(self, problem_id: int, package_id: int, package_type: str = 'linux'):
        """Download a package into a temporary file. Caller must close the returned file."""
        response = self._post('problem.package', {
            'problemId': problem_id, 'packageId': package_id, 'type': package_type,
        }, stream=True)
        out = tempfile.TemporaryFile(suffix='.zip')
        try:
            for chunk in response.iter_content(1 << 20):
                out.write(chunk)
            out.seek(0)
            if out.read(2) != ZIP_MAGIC:
                out.seek(0)
                snippet = out.read(300).decode('utf-8', 'replace')
                raise PolygonAPIError(f'problem.package did not return a zip (HTTP {response.status_code}): {snippet}')
            out.seek(0)
            return out
        except BaseException:
            out.close()
            raise
        finally:
            response.close()

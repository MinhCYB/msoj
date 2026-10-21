import logging
from contextlib import contextmanager
from typing import List

from celery import shared_task
from django.db import connection

from judge.models import PolygonProblem
from judge.utils.polygon_sync import PolygonSync

__all__ = ('polygon_refresh_index', 'polygon_sync_all', 'polygon_sync_problems', 'polygon_sync_busy')

logger = logging.getLogger('judge.polygon')

LOCK_NAME = 'msoj_polygon_sync'


def _lock_supported() -> bool:
    return connection.vendor == 'mysql'


def polygon_sync_busy() -> bool:
    """True while some process holds the sync lock."""
    if not _lock_supported():
        return False
    with connection.cursor() as cursor:
        cursor.execute('SELECT IS_FREE_LOCK(%s)', [LOCK_NAME])
        return cursor.fetchone()[0] != 1


@contextmanager
def _exclusive():
    """
    Only one Polygon sync may run at a time: Polygon rate-limits per key and two imports of the same problem
    would race on its data directory. A MySQL named lock is shared by every worker process and is released
    automatically if the worker dies.
    """
    if not _lock_supported():
        yield True
        return
    with connection.cursor() as cursor:
        cursor.execute('SELECT GET_LOCK(%s, 0)', [LOCK_NAME])
        acquired = cursor.fetchone()[0] == 1
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute('SELECT RELEASE_LOCK(%s)', [LOCK_NAME])


@shared_task
def polygon_refresh_index(refresh_tags: bool = False) -> str:
    with _exclusive() as acquired:
        if not acquired:
            return 'busy'
        PolygonSync(log=logger.info).refresh_index(refresh_tags=refresh_tags)
        return 'ok'


@shared_task
def polygon_sync_all(force: bool = False) -> str:
    with _exclusive() as acquired:
        if not acquired:
            return 'busy'
        sync = PolygonSync(log=logger.info)
        rows = sync.refresh_index()
        logger.info('Polygon sync finished: %s', sync.sync_all(rows, force=force))
        return 'ok'


@shared_task
def polygon_sync_problems(polygon_ids: List[int], force: bool = False) -> str:
    with _exclusive() as acquired:
        if not acquired:
            return 'busy'
        sync = PolygonSync(log=logger.info)
        rows = PolygonProblem.objects.filter(polygon_id__in=polygon_ids)
        for pp in rows:
            sync.sync_problem(pp, force=force)
        return 'ok'

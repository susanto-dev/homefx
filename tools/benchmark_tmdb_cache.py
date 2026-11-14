"""Measure fabricated cache workload locally; never use TMDB or account data.

Times are development-machine observations, not network, image-decoding or TV
performance. Output contains aggregate counts only. Temporary data is removed.
"""
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.tmdb_artwork import Artwork
from resources.lib.tmdb_cache import ArtworkCache


def measure():
    with tempfile.TemporaryDirectory() as profile:
        cache = ArtworkCache(profile)
        keys = [('movie', ident, 'en-US') for ident in range(1, 101)]
        calls = 0
        def fetch(_):
            nonlocal calls
            calls += 1
            return Artwork('/SyntheticPoster.jpg', '/SyntheticBackdrop.jpg')
        start = time.perf_counter()
        for _ in range(5):
            cache.refresh(keys, fetch)
        cold = time.perf_counter() - start
        start = time.perf_counter()
        rows = cache.read_many(keys)
        warm = time.perf_counter() - start
        before = calls
        refresh_start = time.perf_counter()
        cache.refresh(keys, fetch)
        warm_refresh = time.perf_counter() - refresh_start
        start = time.perf_counter()
        for _ in range(5):
            cache.read_many(keys)
        multiple = time.perf_counter() - start
        size = (Path(profile) / 'tmdb-artwork/paths.sqlite3').stat().st_size
        return {'synthetic_titles': len(rows), 'cold_fetch_calls': before,
                'warm_fetch_calls': calls - before, 'database_bytes': size,
                'cold_fill_seconds': round(cold, 6), 'warm_read_seconds': round(warm, 6),
                'warm_refresh_seconds': round(warm_refresh, 6),
                'five_row_reads_seconds': round(multiple, 6), 'live_network': False,
                'tv_measurement': False}


if __name__ == '__main__':
    print(json.dumps(measure(), indent=2))

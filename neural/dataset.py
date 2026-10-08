"""Public WTHOR download, reconstruction, grouped split and symmetry leakage audit."""
import argparse
import hashlib
import json
import struct
import urllib.request
from pathlib import Path
from engine.board import Board
from experiments.tournament import digest

SOURCE = 'https://www.ffothello.org/wthor/base/WTH_2021.wtb'


def symmetries(values):
    variants = []
    for reflect in (False, True):
        for rotation in range(4):
            transformed = [0] * 64
            for i, value in enumerate(values):
                r, c = divmod(i, 8)
                if reflect:
                    c = 7 - c
                for _ in range(rotation):
                    r, c = c, 7 - r
                transformed[r * 8 + c] = value
            variants.append(tuple(transformed))
    return tuple(variants)


def encoding(board):
    # Relative colors encode the side to move implicitly. No 65th input needed.
    return tuple(x * board.turn for x in board.cells)


def parse_wthor(payload):
    if len(payload) < 16:
        raise ValueError('Truncated WTHOR header')
    count = struct.unpack_from('<I', payload, 4)[0]
    if payload[12] not in (0, 8) or payload[13] != 0 or len(payload) != 16 + 68 * count:
        raise ValueError('Expected a standard 8×8 WTHOR game file of matching size')
    for i in range(count):
        record = payload[16 + i * 68:16 + (i + 1) * 68]
        score = record[6]
        if not 0 <= score <= 64:
            raise ValueError('Invalid recorded black score')
        moves, ended = [], False
        for code in record[8:]:
            if code == 0:
                ended = True
                continue
            r, c = divmod(code, 10)
            if ended or not (1 <= r <= 8 and 1 <= c <= 8):
                raise ValueError('Invalid move encoding or nonzero move after padding')
            moves.append((r - 1) * 8 + c - 1)
        yield i, score, moves


class NearIndex:
    """Three disjoint bands: distance <=2 guarantees at least one equal band."""
    def __init__(self):
        self.bands = ({}, {}, {})
        self.rows = []

    @staticmethod
    def keys(values):
        return (values[:22], values[22:43], values[43:])

    def contains_near(self, values):
        for variant in symmetries(values):
            candidates = set()
            for band, key in zip(self.bands, self.keys(variant)):
                candidates.update(band.get(key, ()))
            for i in candidates:
                if sum(x != y for x, y in zip(variant, self.rows[i])) <= 2:
                    return True
        return False

    def add(self, values):
        index = len(self.rows)
        self.rows.append(values)
        for band, key in zip(self.bands, self.keys(values)):
            band.setdefault(key, []).append(index)


def download(path, expected_sha256=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        request = urllib.request.Request(SOURCE, headers={'User-Agent': 'othello-ai academic research'})
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
        list(parse_wthor(payload))  # validate before installing the cache
        path.write_bytes(payload)
    actual = digest(path)
    if expected_sha256 and actual != expected_sha256:
        raise ValueError(f'Dataset hash mismatch: expected {expected_sha256}, got {actual}')
    return path


def preprocess(raw='data/raw/WTH_2021.wtb', output='data/processed', seed=730, limit=None, expected_sha256=None):
    if type(seed) is not int or (limit is not None and (type(limit) is not int or limit < 1)):
        raise ValueError('Integer seed and positive integer game limit required')
    path = download(raw, expected_sha256)
    groups, rejected = {}, []
    for index, score, moves in parse_wthor(path.read_bytes()):
        if limit is not None and index >= limit:
            break
        b, samples, prefix = Board.initial(), [], None
        try:
            for ply, move in enumerate(moves, 1):
                if not b.legal_moves():
                    b = b.play(None)
                b = b.play(move)
                if ply == 12:
                    prefix = min(symmetries(encoding(b)))
                if ply >= 16 and ply % 4 == 0:
                    samples.append({'x': encoding(b), 'y': ((score > 32) - (score < 32)) * b.turn,
                                    'game': index, 'ply': ply})
            if prefix is None or not samples:
                raise ValueError('Too short to sample')
            # Whole games sharing a symmetric 12-placement position stay together.
            group = hashlib.sha256(bytes(x + 1 for x in prefix)).hexdigest()
            groups.setdefault(group, []).extend(samples)
        except ValueError as exc:
            rejected.append({'game': index, 'reason': str(exc)})
    splits = {'train': [], 'validation': [], 'test': []}
    group_counts = dict.fromkeys(splits, 0)
    for group, rows in sorted(groups.items()):
        bucket = int(hashlib.sha256(f'{seed}:{group}'.encode()).hexdigest()[:8], 16) % 100
        split = 'train' if bucket < 70 else 'validation' if bucket < 85 else 'test'
        group_counts[split] += 1
        splits[split].extend(rows)
    directory, index = Path(output), NearIndex()
    directory.mkdir(parents=True, exist_ok=True)
    removals, counts, hashes, prepared = {}, {}, {}, {}
    for split, rows in splits.items():
        kept, seen, removed = [], set(), 0
        for row in rows:
            canonical = min(symmetries(row['x']))
            if canonical in seen or (split != 'train' and index.contains_near(canonical)):
                removed += 1
                continue
            seen.add(canonical)
            kept.append(row)
        # Index only prior splits; within-split near neighbors are legitimate.
        for row in kept:
            index.add(min(symmetries(row['x'])))
        if not kept:
            raise ValueError(f'Empty {split} split; use more source games')
        payload = ''.join(json.dumps(row) + '\n' for row in kept)
        prepared[split] = payload
        removals[split], counts[split], hashes[split] = removed, len(kept), hashlib.sha256(payload.encode()).hexdigest()
    # Validate every split before replacing any previously valid processed file.
    for split, payload in prepared.items():
        (directory / f'{split}.jsonl').write_text(payload)
    manifest = {'source': SOURCE, 'raw_sha256': digest(path), 'seed': seed, 'limit': limit,
                'target': 'recorded game outcome from side-to-move perspective: loss=-1, draw=0, win=1',
                'sampling': 'every fourth placement from placement 16', 'features': 64,
                'grouping': 'symmetric position after 12 placements; whole games grouped',
                'leakage_policy': 'within-split symmetric duplicates keep first; later splits discard distance <=2 from any earlier split under all eight board symmetries',
                'counts': counts, 'group_counts': group_counts, 'removed': removals,
                'processed_sha256': hashes, 'rejected_games': rejected}
    (directory / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    if directory.resolve() == Path('data/processed').resolve():
        report = Path('experiments/results/dataset_manifest.json')
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(manifest, indent=2))
    print(json.dumps({'counts': counts, 'removed': removals, 'rejected': len(rejected)}), flush=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', type=int, default=730)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--sha256')
    args = parser.parse_args()
    preprocess(seed=args.seed, limit=args.limit, expected_sha256=args.sha256)

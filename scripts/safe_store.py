"""Standard-library storage primitives for the private experience profile.

Supports atomic writes, optimistic CAS, journaled transactions and recovery,
plus path/symlink/lock safety for the local profile root. No network, no
privileged bridge, and no importing of executable content from packs.
"""
from __future__ import annotations
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import time
import uuid

STATE = '.wb-state'
PLAN = '.maintenance-plan.json'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')

def relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise ValueError(f'Unsafe relative path: {value!r}')
    parts = value.split('/')
    if PureWindowsPath(value).anchor or any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in parts):
        raise ValueError(f'Unsafe relative path: {value!r}')
    if any(re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', p, re.I) for p in parts):
        raise ValueError(f'Reserved path: {value!r}')
    return Path(*parts)

def no_links(path):
    path = Path(path).absolute()
    for part in [*reversed(path.parents), path]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue  # New write targets may not exist yet; other errors fail closed.
        # One fresh metadata read per component; never cache across operations.
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError(f'Links/reparse points are unsupported: {part}')
        if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
            raise ValueError(f'Hard links are unsupported: {part}')
    return path

def inside(root, rel):
    root = no_links(root).resolve()
    target = no_links(root / relative(rel))
    if not target.resolve().is_relative_to(root):
        raise ValueError('Path escaped root')
    return target

def hash_file(path):
    no_links(path)
    return digest(Path(path).read_bytes()) if Path(path).is_file() else None

def atomic_bytes(path, data, delays=(0.1, 0.1, 0.2, 0.4)):
    path = no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        with temp.open('xb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        for attempt in range(len(delays) + 1):
            try:
                os.replace(temp, path)
                break
            except PermissionError:
                if os.name != 'nt' or attempt == len(delays):
                    raise
                time.sleep(delays[attempt])
        if os.name != 'nt':
            fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    except BaseException as exc:
        # Retain a completed or partial candidate for diagnosis; never truncate old data.
        raise OSError(f'Write deferred; original retained when replace failed; candidate={temp}: {exc}') from exc

@contextlib.contextmanager
def locked(root):
    lock = inside(root, STATE + '/lock')
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open('a+b') as handle:
        if lock.stat().st_size == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('Another writer holds the skill lock') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

def pending(root):
    base = inside(root, STATE + '/transactions')
    result = []
    for path in sorted(base.glob('*/journal.json')):
        no_links(path)
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['status'] not in ('committed', 'rolled-back'):
            result.append(path.parent.name)
    return result

def recover(root, txid):
    if not re.fullmatch('[a-f0-9]{32}', txid):
        raise ValueError('Invalid transaction ID')
    with locked(root):
        tx = inside(root, STATE + '/transactions/' + txid)
        journal = json.loads((tx / 'journal.json').read_text(encoding='utf-8'))
        _rollback(root, tx, journal)

def _rollback(root, tx, journal):
    for rel, item in journal['files'].items():
        target = inside(root, rel)
        if hash_file(target) not in (item['before'], item['after']):
            raise ValueError(f'Recovery refuses independently changed file: {rel}')
    for rel, item in reversed(list(journal['files'].items())):
        target = inside(root, rel)
        if hash_file(target) == item['before']:
            continue
        if item['before'] is None:
            target.unlink()  # undo only a new file created by this transaction
        else:
            backup = inside(tx, 'before/' + rel)
            data = backup.read_bytes()
            if digest(data) != item['before']:
                raise ValueError('Invalid recovery backup')
            atomic_bytes(target, data)
    journal['status'] = 'rolled-back'
    atomic_bytes(tx / 'journal.json', json_bytes(journal))

def apply(root, writes, expected, deletes=(), *, already_locked=False):
    """Optimistic compare-and-swap + durable backups. Failure blocks further writes until recovered."""
    root = no_links(root).resolve()
    writes = dict(writes)
    deletes = list(deletes)
    if set(writes) & set(deletes) or set(expected) != set(writes) | set(deletes):
        raise ValueError('Plan must bind every write/delete exactly once')
    for rel in expected:
        inside(root, rel)
        if rel.split('/')[0] == STATE:
            raise ValueError('Cannot modify transaction internals')
    guard = contextlib.nullcontext() if already_locked else locked(root)
    with guard:
        if pending(root):
            raise ValueError('Unfinished transaction; recover it before new writes')
        for rel, old in expected.items():
            if hash_file(inside(root, rel)) != old:
                raise ValueError(f'Stale plan; target changed: {rel}')
        txid = uuid.uuid4().hex
        tx = inside(root, STATE + '/transactions/' + txid)
        tx.mkdir(parents=True)
        journal = {'status': 'prepared', 'files': {}}
        for rel, old in expected.items():
            if old is not None:
                atomic_bytes(inside(tx, 'before/' + rel), inside(root, rel).read_bytes())
            journal['files'][rel] = {'before': old, 'after': digest(writes[rel]) if rel in writes else None}
        atomic_bytes(tx / 'journal.json', json_bytes(journal))
        try:
            for rel, data in writes.items():
                atomic_bytes(inside(root, rel), data)
            for rel in deletes:
                target = inside(root, rel)
                if target.exists():
                    target.unlink()
            for rel, item in journal['files'].items():
                if hash_file(inside(root, rel)) != item['after']:
                    raise ValueError(f'Verification failed: {rel}')
            journal['status'] = 'committed'
            atomic_bytes(tx / 'journal.json', json_bytes(journal))
        except BaseException:
            try:
                _rollback(root, tx, journal)
            except BaseException:
                # The prepared journal remains durable and blocks subsequent writes.
                pass
            raise
        return txid

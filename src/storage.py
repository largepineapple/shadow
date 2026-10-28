import hashlib
import json
import sqlite3
from contextlib import contextmanager


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Storage:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS drafts (id INTEGER PRIMARY KEY, idempotency_key TEXT UNIQUE NOT NULL, request_id TEXT NOT NULL, material_id TEXT NOT NULL, platform TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL);''')

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield self.db
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def drafts(self):
        return [dict(x) for x in self.db.execute('SELECT * FROM drafts')]

    def close(self):
        self.db.close()

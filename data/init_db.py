#!/usr/bin/env python3
"""Initialize the FTS5 knowledge base from seed.jsonl.

Usage:
    python data/init_db.py              # uses default paths
    python data/init_db.py --seed path/to/seed.jsonl --db path/to/knowledge.db

The database is created fresh each run. Existing tables are dropped first.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


SEED_PATH = Path(__file__).resolve().parent / "seed.jsonl"
DB_PATH = Path(__file__).resolve().parent / "knowledge.db"


DDL = """
DROP TABLE IF EXISTS documents_fts;
DROP TABLE IF EXISTS documents;

CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    location TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE documents_fts USING fts5(
    source_id,
    location,
    text,
    content='documents',
    content_rowid='id',
    tokenize='porter unicode61'
);
"""


def init_db(seed_path: Path = SEED_PATH, db_path: Path = DB_PATH) -> int:
    """Create the database, load seed documents, backfill FTS. Returns row count."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(DDL)

    rows = []
    with open(seed_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rows.append((rec["source_id"], rec["location"], rec["text"]))

    conn.executemany(
        "INSERT INTO documents (source_id, location, text) VALUES (?, ?, ?)",
        rows,
    )

    # Explicit FTS backfill — ensures MATCH works immediately after init
    conn.execute("""
        INSERT INTO documents_fts(rowid, source_id, location, text)
        SELECT id, source_id, location, text FROM documents
    """)

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize FTS5 knowledge base")
    parser.add_argument("--seed", type=Path, default=SEED_PATH, help="Path to seed JSONL")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Output database path")
    args = parser.parse_args()

    count = init_db(args.seed, args.db)
    print(f"Database initialized: {args.db}")
    print(f"Documents loaded: {count}")


if __name__ == "__main__":
    main()

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from app.schemas.domain import utcnow

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, input_json TEXT NOT NULL, status TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, state_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS searches (
 id TEXT, run_id TEXT REFERENCES runs(id), query TEXT, engine TEXT, response_metadata TEXT,
 created_at TEXT, PRIMARY KEY(run_id,id)
);
CREATE TABLE IF NOT EXISTS sources (
 id TEXT, run_id TEXT REFERENCES runs(id), url TEXT, title TEXT, publisher TEXT,
 retrieved_at TEXT, content_hash TEXT, payload_json TEXT, PRIMARY KEY(run_id,id)
);
CREATE TABLE IF NOT EXISTS facts (
 id TEXT, run_id TEXT REFERENCES runs(id), source_id TEXT, subject TEXT, field TEXT,
 value TEXT, evidence_span TEXT, confidence TEXT, status TEXT, payload_json TEXT,
 PRIMARY KEY(run_id,id)
);
CREATE TABLE IF NOT EXISTS offers (
 id TEXT, run_id TEXT REFERENCES runs(id), title TEXT, manufacturer TEXT, part_number TEXT,
 price TEXT, currency TEXT, seller TEXT, url TEXT, identity_status TEXT, payload_json TEXT,
 PRIMARY KEY(run_id,id)
);
CREATE TABLE IF NOT EXISTS checks (
 id TEXT, run_id TEXT REFERENCES runs(id), check_type TEXT, required_fact TEXT, observed_fact TEXT,
 status TEXT, explanation TEXT, source_ids TEXT, payload_json TEXT, PRIMARY KEY(run_id,id)
);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER, run_id TEXT REFERENCES runs(id), event_type TEXT, message TEXT,
 created_at TEXT, payload_json TEXT, PRIMARY KEY(run_id,id)
);
CREATE INDEX IF NOT EXISTS facts_by_run ON facts(run_id);
"""

class SQLiteStore:
    def __init__(self,path: Path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=RLock()
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        with self.lock:
            connection=sqlite3.connect(self.path,timeout=5)
            connection.row_factory=sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            try:
                with connection:
                    yield connection
            finally:
                connection.close()

    def get(self,run_id):
        with self.connect() as db:
            row=db.execute("SELECT state_json FROM runs WHERE id=?",(run_id,)).fetchone()
        return json.loads(row["state_json"]) if row else None

    def save(self,state):
        run_id=state["run_id"]
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET input_json=excluded.input_json,status=excluded.status,updated_at=excluded.updated_at,state_json=excluded.state_json",
              (run_id,json.dumps(state["input"]),state["status"],state["created_at"],state["updated_at"],json.dumps(state)))
            for table in ("searches","sources","facts","offers","checks","events"):
                db.execute(f"DELETE FROM {table} WHERE run_id=?",(run_id,))
            for s in state["searches"]:
                db.execute("INSERT INTO searches VALUES(?,?,?,?,?,?)",(s["id"],run_id,s.get("query"),s.get("engine"),json.dumps(s),s.get("created_at")))
            for s in state["sources"]:
                db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?,?)",(s["id"],run_id,s["url"],s["title"],s["publisher"],s["retrieved_at"],s["content_hash"],json.dumps(s)))
            for f in state["facts"]:
                db.execute("INSERT INTO facts VALUES(?,?,?,?,?,?,?,?,?,?)",(f["id"],run_id,f["source_id"],f["subject"],f["field"],json.dumps(f["value"]),f["evidence_span"],f["confidence"],f["status"],json.dumps(f)))
            for o in state["offers"]:
                db.execute("INSERT INTO offers VALUES(?,?,?,?,?,?,?,?,?,?,?)",(o["id"],run_id,o["title"],o["manufacturer"],o["part_number"],o["price"],o["currency"],o["seller"],o["url"],o["identity_status"],json.dumps(o)))
            for c in state["checks"]:
                db.execute("INSERT INTO checks VALUES(?,?,?,?,?,?,?,?,?)",(c["id"],run_id,c["check_type"],json.dumps(c["required"]),json.dumps(c["observed"]),c["status"],c["explanation"],json.dumps(c["source_ids"]),json.dumps(c)))
            for e in state["events"]:
                db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)",(e["id"],run_id,e["event_type"],e["message"],e["created_at"],json.dumps(e)))

    def recover(self):
        with self.connect() as db:
            rows=db.execute("SELECT state_json FROM runs WHERE status='investigating'").fetchall()
        for row in rows:
            state=json.loads(row["state_json"])
            state["status"]="interrupted"
            state["updated_at"]=utcnow()
            state["events"].append({"id":len(state["events"])+1,"event_type":"warning","stage":"interrupted",
                "message":"The server restarted during this investigation. Stored evidence is preserved; start a fresh run for new retrieval.",
                "created_at":utcnow()})
            self.save(state)

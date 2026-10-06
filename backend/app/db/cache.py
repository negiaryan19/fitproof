import hashlib
import json
import time

class SearchCache:
    def __init__(self,store,ttl=3600):
        self.store=store
        self.ttl=ttl
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS search_cache (key TEXT PRIMARY KEY, created_at REAL, response TEXT)')

    def key(self,params):
        return hashlib.sha256(json.dumps(params,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    def get(self,params):
        if self.ttl<=0:
            return None
        with self.store.connect() as db:
            row=db.execute('SELECT created_at,response FROM search_cache WHERE key=?',(self.key(params),)).fetchone()
        if not row or time.time()-row['created_at']>self.ttl:
            return None
        return json.loads(row['response'])

    def set(self,params,response):
        if self.ttl<=0:
            return
        with self.store.connect() as db:
            db.execute('INSERT INTO search_cache VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET created_at=excluded.created_at,response=excluded.response',(self.key(params),time.time(),json.dumps(response)))

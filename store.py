import sqlite3, json, os
from datetime import datetime, timezone
from pathlib import Path
DB=os.environ.get('DATABASE_PATH', str(Path(__file__).parent/'data/tracker.sqlite3'))
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def connect():
 c=sqlite3.connect(DB, timeout=30); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
def init():
 Path(DB).parent.mkdir(parents=True,exist_ok=True)
 with connect() as c:
  c.executescript('''
  PRAGMA journal_mode=WAL;
  CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY, applied_at TEXT);
  CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS opportunities(id INTEGER PRIMARY KEY, employer TEXT NOT NULL,role TEXT NOT NULL,city TEXT DEFAULT '',category TEXT DEFAULT 'Economic consulting',url TEXT DEFAULT '',requisition TEXT DEFAULT '',cycle TEXT DEFAULT '2027',recruiting TEXT DEFAULT 'Monitor',deadline TEXT,authorization TEXT DEFAULT 'Employer support unknown',outside_quebec TEXT DEFAULT 'Unconfirmed',support TEXT DEFAULT 'Unknown',summary TEXT DEFAULT '',fit TEXT DEFAULT '',dates TEXT DEFAULT '',requirements TEXT DEFAULT '',compensation TEXT DEFAULT '',evidence TEXT DEFAULT '',first_discovered TEXT NOT NULL,last_verified TEXT,updated TEXT NOT NULL,origin TEXT DEFAULT 'manual');
  CREATE UNIQUE INDEX IF NOT EXISTS canonical_job ON opportunities(url,cycle) WHERE url != '' AND recruiting != 'Monitor';
  CREATE TABLE IF NOT EXISTS tracking(opportunity_id INTEGER PRIMARY KEY REFERENCES opportunities(id) ON DELETE CASCADE,application TEXT DEFAULT 'Saved',outreach TEXT DEFAULT 'Not started',priority INTEGER DEFAULT 3,notes TEXT DEFAULT '',next_action TEXT DEFAULT '',due TEXT,applied_date TEXT,interview_date TEXT,resume TEXT DEFAULT '',cover_letter TEXT DEFAULT '',saved INTEGER DEFAULT 1);
  CREATE TABLE IF NOT EXISTS contacts(id INTEGER PRIMARY KEY,name TEXT NOT NULL,title TEXT DEFAULT '',employer TEXT DEFAULT '',office TEXT DEFAULT '',category TEXT DEFAULT '',tags TEXT DEFAULT '',profile TEXT DEFAULT '',email TEXT DEFAULT '',sources TEXT DEFAULT '',verified TEXT,reason TEXT DEFAULT '',channel TEXT DEFAULT '',response TEXT DEFAULT '',notes TEXT DEFAULT '',followup TEXT);
  CREATE TABLE IF NOT EXISTS contact_opportunities(contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE CASCADE,PRIMARY KEY(contact_id,opportunity_id));
  CREATE TABLE IF NOT EXISTS interactions(id INTEGER PRIMARY KEY,contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,date TEXT NOT NULL,channel TEXT DEFAULT '',notes TEXT DEFAULT '',response TEXT DEFAULT '',followup TEXT);
  CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY,name TEXT NOT NULL,url TEXT NOT NULL UNIQUE,kind TEXT DEFAULT 'page',employer TEXT DEFAULT '',attempted TEXT,verified TEXT,error TEXT,excerpt TEXT DEFAULT '',digest TEXT DEFAULT '');
  CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,started TEXT NOT NULL,finished TEXT,status TEXT NOT NULL,summary TEXT DEFAULT '');
  CREATE TABLE IF NOT EXISTS changes(id INTEGER PRIMARY KEY,opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE CASCADE,at TEXT NOT NULL,field TEXT NOT NULL,previous TEXT,current TEXT);
  INSERT OR IGNORE INTO migrations VALUES(1,datetime('now'));
  ''')
  columns={r['name'] for r in c.execute('PRAGMA table_info(opportunities)')}
  if 'published_date' not in columns:
   c.execute('ALTER TABLE opportunities ADD COLUMN published_date TEXT')
  c.execute("INSERT OR IGNORE INTO migrations VALUES(2,datetime('now'))")
  if 'deleted' not in {r['name'] for r in c.execute('PRAGMA table_info(tracking)')}:
   c.execute('ALTER TABLE tracking ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0')
  c.execute("INSERT OR IGNORE INTO migrations VALUES(3,datetime('now'))")
  columns={r['name'] for r in c.execute('PRAGMA table_info(opportunities)')}
  for name in ('recruitment_contact','recruitment_contact_details'):
   if name not in columns:c.execute(f"ALTER TABLE opportunities ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
  c.execute("INSERT OR IGNORE INTO migrations VALUES(4,datetime('now'))")
  if not c.execute('SELECT 1 FROM sources').fetchone():
   sources=[('Analysis Group','https://www.analysisgroup.com/careers/'),('NERA','https://www.nera.com/why-nera.html'),('CRA','https://www.crai.com/careers/'),('Compass Lexecon','https://www.compasslexecon.com/careers/'),('Brattle','https://www.brattle.com/careers/'),('Bank of Canada','https://www.bankofcanada.ca/careers/'),('IRCC Francophone Mobility','https://www.canada.ca/en/immigration-refugees-citizenship/services/work-canada/hire-temporary-foreign/french-speaking-bilingual-workers-outside-quebec/hire.html')]
   for name,url in sources: c.execute('INSERT INTO sources(name,url,employer) VALUES(?,?,?)',(name,url,name))
def rows(sql,args=()):
 with connect() as c:return [dict(r) for r in c.execute(sql,args)]
def upsert_research(c, item):
 # A URL + cycle or employer + requisition + cycle identifies a posting across refreshes.
 existing=c.execute('SELECT * FROM opportunities WHERE (url=? AND url!=? AND cycle=?) OR (employer=? AND requisition=? AND requisition!=? AND cycle=?)',(item['url'],'',item.get('cycle','2027'),item['employer'],item.get('requisition',''),'',item.get('cycle','2027'))).fetchone()
 stamp=now()
 if existing:
  for key,value in item.items():
   if key not in existing.keys():raise ValueError('Unknown research field')
   if key in {'id','origin','first_discovered','updated','last_verified'}:continue
   if existing[key]!=value:
    c.execute('INSERT INTO changes(opportunity_id,at,field,previous,current) VALUES(?,?,?,?,?)',(existing['id'],stamp,key,str(existing[key] or ''),str(value or '')))
    c.execute(f'UPDATE opportunities SET {key}=? WHERE id=?',(value,existing['id']))
  c.execute('UPDATE opportunities SET last_verified=?,updated=? WHERE id=?',(stamp,stamp,existing['id'])); return existing['id']
 item={**item,'first_discovered':stamp,'updated':stamp,'last_verified':stamp,'origin':'research'}
 keys=list(item);cur=c.execute(f"INSERT INTO opportunities({','.join(keys)}) VALUES({','.join('?' for _ in keys)})",list(item.values()));oid=cur.lastrowid
 c.execute('INSERT INTO tracking(opportunity_id,saved) VALUES(?,0)',(oid,));c.execute('INSERT INTO changes(opportunity_id,at,field,current) VALUES(?,?,?,?)',(oid,stamp,'discovered',item['role']));return oid
TABLES=['settings','opportunities','tracking','contacts','contact_opportunities','interactions','sources','runs','changes']
def backup():return {'version':1,'exported_at':now(),'tables':{t:rows(f'SELECT * FROM {t}') for t in TABLES}}
def restore(payload):
 if payload.get('version')!=1 or set(payload.get('tables',{}))!=set(TABLES):raise ValueError('Unsupported or incomplete backup')
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  for t in reversed(TABLES):c.execute(f'DELETE FROM {t}')
  for t in TABLES:
   allowed={r['name'] for r in c.execute(f'PRAGMA table_info({t})')}
   for row in payload['tables'][t]:
    if not row or not set(row)<=allowed:raise ValueError('Invalid backup columns')
    c.execute(f"INSERT INTO {t}({','.join(row)}) VALUES({','.join('?' for _ in row)})",list(row.values()))
  if c.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('Broken backup relationships')

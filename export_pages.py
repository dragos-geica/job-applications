"""Build Pages using a disposable research-only database. Never open the private tracker."""
import os,tempfile,json,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as tmp:
 os.environ['DATABASE_PATH']=str(Path(tmp)/'public.sqlite3')
 import store,research,seed_research
 store.init()
 snapshot=root/'public-research/research.json'
 if snapshot.exists():
  old=json.loads(snapshot.read_text())
  with store.connect() as c:
   for table in ['changes','opportunities','sources','runs']:
    if table=='opportunities':c.execute('DELETE FROM tracking')
    c.execute(f'DELETE FROM {table}')
   for table in ['opportunities','sources','runs','changes']:
    for row in old.get(table,[]):
     c.execute(f"INSERT INTO {table}({','.join(row)}) VALUES({','.join('?' for _ in row)})",list(row.values()))
   for row in old.get('opportunities',[]):c.execute('INSERT INTO tracking(opportunity_id,saved) VALUES(?,0)',(row['id'],))
 seed_research.seed()
 research.refresh()
 data={t:store.rows(f'SELECT * FROM {t}') for t in ['opportunities','sources','changes','runs']}
 for s in data['sources']:
  if s.get('error'):s['error']='Source check failed; last successful information retained.'
 data['generated_at']=store.now()
 snapshot.write_text(json.dumps(data,ensure_ascii=False,indent=2))
 dest=root/'_site';dest.mkdir(exist_ok=True)
 html=(root/'templates/index.html').read_text().replace('{{csrf}}','pages').replace('/static/','./static/').replace('<script defer src="./static/app.js">','<script defer src="./static/pages.js"></script><script defer src="./static/app.js">').replace('Dragoș Geica<br><small>Wesleyan University · 2028</small>','Browser workspace<br><small>Personal data stays on this device</small>').replace('id="logout">Sign out','id="logout" hidden>Sign out').replace('Private by design ·','Tracking saved in this browser · Export backups regularly ·')
 (dest/'index.html').write_text(html);shutil.copytree(root/'static',dest/'static',dirs_exist_ok=True)
 shutil.copyfile(snapshot,dest/'research.json');(dest/'.nojekyll').touch()
 print(f"Built public site: {len(data['opportunities'])} research records. No personal tracking exported.")

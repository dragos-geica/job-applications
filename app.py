import os,json,secrets,csv,io,time,threading
from datetime import timedelta,datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask,request,session,jsonify,render_template,redirect,Response,abort
from werkzeug.security import generate_password_hash,check_password_hash
import store,research
APPLICATIONS=['Saved','Preparing','Applied','Interviewing','Offer','Rejected','Withdrawn']
OUTREACH=['Not started','Contact identified','Contacted','Replied','Call scheduled','Follow-up due','Complete']
RECRUITING=['Confirmed Summer 2027','Dates unclear','Monitor','Closed / archived']
AUTH=['Employer support unknown','Employer support confirmed','Existing Canadian work authorization required','Canadian co-op/enrollment restriction','Citizenship, residency, or clearance restriction','Needs clarification']
def create_app(test_config=None):
 store.init();app=Flask(__name__)
 keyfile=Path(store.DB).parent/'session.key'
 if not keyfile.exists():
  fd=os.open(keyfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w') as f:f.write(secrets.token_hex(32))
 app.config.update(SECRET_KEY=keyfile.read_text(),SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','0')=='1',PERMANENT_SESSION_LIFETIME=timedelta(hours=12),MAX_CONTENT_LENGTH=10*1024*1024)
 if test_config:app.config.update(test_config)
 attempts={};guard=threading.Lock()
 def auth_hash():
  p=Path(store.DB).parent/'password.hash';return p.read_text().strip() if p.exists() else None
 @app.before_request
 def protect():
  if request.path=='/favicon.ico':return Response(status=204)
  if request.path.startswith('/static/'):return
  if request.path=='/login':return
  if not session.get('authenticated'):
   if request.path.startswith('/api/'):return jsonify(error='Login required'),401
   return redirect('/login')
  if request.method not in ('GET','HEAD','OPTIONS') and not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),session.get('csrf','!')):abort(403)
 @app.after_request
 def headers(r):
  r.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"});return r
 @app.errorhandler(400)
 @app.errorhandler(403)
 @app.errorhandler(404)
 @app.errorhandler(413)
 def error(e):return jsonify(error=e.description),e.code
 @app.route('/login',methods=['GET','POST'])
 def login():
  if request.method=='GET':
   session.setdefault('login_csrf',secrets.token_hex(24))
   return render_template('login.html',csrf=session['login_csrf'],configured=bool(auth_hash()))
  if not secrets.compare_digest(request.form.get('csrf',''),session.get('login_csrf','!')):abort(403)
  ip=request.remote_addr
  with guard:
   recent=[x for x in attempts.get(ip,[]) if time.time()-x<900];attempts[ip]=recent
   if len(recent)>=10:return 'Too many attempts. Retry in 15 minutes.',429
   recent.append(time.time())
  h=auth_hash()
  if h and check_password_hash(h,request.form.get('password','')):
   session.clear();session.update(authenticated=True,csrf=secrets.token_hex(24));session.permanent=True;return redirect('/')
  return render_template('login.html',csrf=session['login_csrf'],configured=bool(h),error='Password not accepted'),401
 @app.post('/api/logout')
 def logout():session.clear();return jsonify(ok=True)
 @app.get('/')
 def index():return render_template('index.html',csrf=session['csrf'])
 @app.get('/api/data')
 def data():
  result={t:store.rows(f'SELECT * FROM {t}') for t in ['contacts','interactions','contact_opportunities','sources','runs','changes']}
  result['opportunities']=store.rows('SELECT o.*,t.* FROM opportunities o JOIN tracking t ON t.opportunity_id=o.id')
  settings={r['key']:r['value'] for r in store.rows('SELECT * FROM settings')}
  heartbeat=settings.get('worker_heartbeat');result.update(settings=settings,worker_active=bool(heartbeat and (datetime.now(timezone.utc)-datetime.fromisoformat(heartbeat)).total_seconds()<120),enums=dict(application=APPLICATIONS,outreach=OUTREACH,recruiting=RECRUITING,authorization=AUTH))
  return jsonify(result)
 def payload(table):
  d=request.get_json();
  if not isinstance(d,dict):abort(400,description='Expected an object')
  with store.connect() as c:allowed={r['name'] for r in c.execute(f'PRAGMA table_info({table})')}-{'id','first_discovered','last_verified','updated','origin','opportunity_id'}
  if not set(d)<=allowed:abort(400,description='Unknown fields')
  for k,v in d.items():
   if v is not None and not isinstance(v,(str,int)):abort(400,description='Invalid field value')
   if isinstance(v,str) and len(v)>20000:abort(400,description='Field too long')
   if k in ('url','profile','resume','cover_letter') and v and urlparse(v).scheme not in ('http','https'):abort(400,description='Links must use HTTPS or HTTP')
   if k in ('due','deadline','published_date','applied_date','interview_date','followup','date','verified') and v:
    try:datetime.fromisoformat(v)
    except ValueError:abort(400,description='Invalid date')
   enums={'application':APPLICATIONS,'outreach':OUTREACH,'recruiting':RECRUITING,'authorization':AUTH}
   if k in enums and v not in enums[k]:abort(400,description='Invalid status')
  return d
 def insert(c,table,d):return c.execute(f"INSERT INTO {table}({','.join(d)}) VALUES({','.join('?' for _ in d)})",list(d.values())).lastrowid
 @app.post('/api/opportunities')
 def new_job():
  d=payload('opportunities')
  if not d.get('employer','').strip() or not d.get('role','').strip():abort(400,description='Employer and role required')
  d.update(first_discovered=store.now(),updated=store.now())
  try:
   with store.connect() as c:
    oid=insert(c,'opportunities',d);c.execute('INSERT INTO tracking(opportunity_id) VALUES(?)',(oid,))
   return jsonify(id=oid),201
  except Exception:return jsonify(error='Duplicate or invalid opportunity'),400
 @app.patch('/api/opportunities/<int:oid>')
 def edit_job(oid):
  d=payload('opportunities')
  if not d:return jsonify(ok=True)
  with store.connect() as c:
   old=c.execute('SELECT * FROM opportunities WHERE id=?',(oid,)).fetchone()
   if not old:abort(404)
   for k,v in d.items():
    if old[k]!=v:c.execute('INSERT INTO changes(opportunity_id,at,field,previous,current) VALUES(?,?,?,?,?)',(oid,store.now(),k,str(old[k] or ''),str(v or '')))
   d['updated']=store.now();c.execute(f"UPDATE opportunities SET {','.join(k+'=?' for k in d)} WHERE id=?",[*d.values(),oid])
  return jsonify(ok=True)
 @app.patch('/api/tracking/<int:oid>')
 def tracking(oid):
  d=payload('tracking')
  if d:
   with store.connect() as c:
    if not c.execute('SELECT 1 FROM tracking WHERE opportunity_id=?',(oid,)).fetchone():abort(404)
    c.execute(f"UPDATE tracking SET {','.join(k+'=?' for k in d)} WHERE opportunity_id=?",[*d.values(),oid])
  return jsonify(ok=True)
 @app.post('/api/contacts')
 def contact():
  d=payload('contacts')
  if not d.get('name','').strip():abort(400,description='Name required')
  with store.connect() as c:cid=insert(c,'contacts',d)
  return jsonify(id=cid),201
 @app.patch('/api/contacts/<int:cid>')
 def edit_contact(cid):
  d=payload('contacts')
  with store.connect() as c:
   if not c.execute('SELECT 1 FROM contacts WHERE id=?',(cid,)).fetchone():abort(404)
   if d:c.execute(f"UPDATE contacts SET {','.join(k+'=?' for k in d)} WHERE id=?",[*d.values(),cid])
  return jsonify(ok=True)
 @app.post('/api/contacts/<int:cid>/interactions')
 def interaction(cid):
  d=payload('interactions');d['contact_id']=cid
  if not d.get('date'):abort(400,description='Interaction date required')
  with store.connect() as c:
   if not c.execute('SELECT 1 FROM contacts WHERE id=?',(cid,)).fetchone():abort(404)
   iid=insert(c,'interactions',d)
   c.execute('UPDATE contacts SET channel=?,response=?,followup=? WHERE id=?',(d.get('channel',''),d.get('response',''),d.get('followup'),cid))
  return jsonify(id=iid),201
 @app.post('/api/contacts/<int:cid>/links')
 def link(cid):
  d=request.get_json()
  try:
   with store.connect() as c:c.execute('INSERT OR IGNORE INTO contact_opportunities VALUES(?,?)',(cid,int(d['opportunity_id'])))
  except Exception:abort(400,description='Invalid contact or opportunity')
  return jsonify(ok=True)
 @app.post('/api/settings')
 def settings():
  d=request.get_json()
  if set(d)-{'permit_status'}:abort(400)
  with store.connect() as c:
   for k,v in d.items():c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(k,str(v)[:500]))
  return jsonify(ok=True)
 @app.post('/api/refresh')
 def refresh():
  threading.Thread(target=research.refresh,daemon=True).start();return jsonify(ok=True,message='Refresh requested; the worker prevents overlapping runs'),202
 @app.get('/api/backup')
 def backup():return Response(json.dumps(store.backup(),ensure_ascii=False),mimetype='application/json',headers={'Content-Disposition':'attachment; filename=internships-backup.json'})
 @app.post('/api/restore')
 def restore():
  try:
   # Keep an automatic pre-restore recovery file outside the served directory.
   recovery=Path(store.DB).parent/('before-restore-'+str(time.time_ns())+'.json')
   with open(recovery,'x',opener=lambda path,flags:os.open(path,flags,0o600)) as f:json.dump(store.backup(),f)
   store.restore(request.get_json())
  except Exception:return jsonify(error='Backup rejected; current database retained'),400
  return jsonify(ok=True)
 @app.get('/api/export/<table>.csv')
 def export(table):
  if table not in ('opportunities','contacts','interactions'):abort(404)
  data=store.rows('SELECT o.*,t.* FROM opportunities o JOIN tracking t ON o.id=t.opportunity_id') if table=='opportunities' else store.rows(f'SELECT * FROM {table}')
  s=io.StringIO();w=csv.writer(s)
  if data:
   w.writerow(data[0].keys())
   for r in data:w.writerow([("'"+str(v)) if str(v or '').startswith(('=','+','-','@','\t','\r')) else v for v in r.values()])
  return Response(s.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename={table}.csv'})
 return app
if __name__=='__main__':
 import sys,getpass
 if '--set-password' in sys.argv:
  store.init();p=getpass.getpass('New private app password (12+ characters): ')
  if len(p)<12:raise SystemExit('Use at least 12 characters')
  path=Path(store.DB).parent/'password.hash'
  with open(path,'w',opener=lambda path,flags:os.open(path,flags,0o600)) as f:f.write(generate_password_hash(p,method='pbkdf2:sha256:1000000'))
  print('Password configured. Existing sessions expire within 12 hours.')
 else:
  from waitress import serve
  serve(create_app(),host=os.getenv('BIND_HOST','127.0.0.1'),port=int(os.getenv('PORT','8000')))

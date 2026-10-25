import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest,store,research
from app import create_app
from werkzeug.security import generate_password_hash
@pytest.fixture
def client(tmp_path,monkeypatch):
 monkeypatch.setattr(store,'DB',str(tmp_path/'test.sqlite3'))
 app=create_app({'TESTING':True});(tmp_path/'password.hash').write_text(generate_password_hash('test-password-123'))
 c=app.test_client();c.get('/login')
 with c.session_transaction() as s:token=s['login_csrf']
 assert c.post('/login',data={'csrf':token,'password':'test-password-123'}).status_code==302
 with c.session_transaction() as s:token=s['csrf']
 c.environ_base['HTTP_X_CSRF_TOKEN']=token
 return c

def job(client):return client.post('/api/opportunities',json={'employer':'Fixture firm','role':'Research intern','city':'Toronto'}).json['id']
def test_auth(client):
 anonymous=client.application.test_client()
 for p in ['/api/data','/api/backup','/api/export/contacts.csv']:assert anonymous.get(p).status_code==401
 assert anonymous.post('/api/opportunities',json={}).status_code==401
 assert client.post('/api/refresh',headers={'X-CSRF-Token':'wrong'},json={}).status_code==403
 assert 'default-src' in client.get('/').headers['Content-Security-Policy']
def test_tracking_contacts_and_relationships(client):
 oid=job(client)
 assert client.patch(f'/api/tracking/{oid}',json={'application':'Applied','outreach':'Contacted','notes':'My private note','due':'2027-01-02','resume':'https://example.org/resume-v1'}).status_code==200
 cid=client.post('/api/contacts',json={'name':'TEST FIXTURE','tags':'Wesleyan University, Romanian connection'}).json['id']
 assert client.post(f'/api/contacts/{cid}/links',json={'opportunity_id':oid}).status_code==200
 assert client.post(f'/api/contacts/{cid}/interactions',json={'date':'2026-10-25','channel':'email','notes':'Fixture conversation','followup':'2026-11-01'}).status_code==201
 d=client.get('/api/data').json
 assert d['opportunities'][0]['application']=='Applied' and d['opportunities'][0]['outreach']=='Contacted'
 assert d['contacts'][0]['followup']=='2026-11-01'
 assert len(d['contact_opportunities'])==1 and len(d['interactions'])==1
 assert 'My private note' in client.get('/api/export/opportunities.csv').text

def fixture_job():return dict(employer='Fixture firm',role='Summer 2027 research intern',city='Toronto',url='https://www.crai.com/fixture',cycle='2027',deadline=None,recruiting='Confirmed Summer 2027',requisition='fixture-001')
def test_refresh_dedupe_changes_preserve_edits(client,monkeypatch):
 j=fixture_job()
 with store.connect() as c:oid=store.upsert_research(c,j)
 client.patch(f'/api/tracking/{oid}',json={'notes':'Keep me','application':'Interviewing','outreach':'Replied'})
 j.update(deadline='2027-01-30')
 with store.connect() as c:
  assert store.upsert_research(c,j)==oid
  j['url']='https://www.crai.com/fixture-new-url';assert store.upsert_research(c,j)==oid
 d=client.get('/api/data').json
 assert len(d['opportunities'])==1 and d['opportunities'][0]['notes']=='Keep me'
 assert any(x['field']=='deadline' and x['current']=='2027-01-30' for x in d['changes'])
 verified=d['opportunities'][0]['last_verified']
 monkeypatch.setattr(research,'fetch',lambda url: (_ for _ in ()).throw(TimeoutError('fixture timeout')))
 research.refresh();d=client.get('/api/data').json
 assert d['opportunities'][0]['recruiting']=='Confirmed Summer 2027'
 assert d['opportunities'][0]['last_verified']==verified
 assert d['runs'][-1]['status']=='Partial'
def test_backup_atomic_restore(client):
 job(client);saved=client.get('/api/backup').json
 job(client);assert len(client.get('/api/data').json['opportunities'])==2
 assert client.post('/api/restore',json=saved).status_code==200
 assert len(client.get('/api/data').json['opportunities'])==1
 bad=json.loads(json.dumps(saved));bad['tables']['tracking'][0]['opportunity_id']=99999
 assert client.post('/api/restore',json=bad).status_code==400
 assert len(client.get('/api/data').json['opportunities'])==1

def test_discovery_geography_dates():
 j={'@type':'JobPosting','title':'Summer 2027 Economics Intern','description':'Undergraduate research','validThrough':'2027-04-01','jobLocation':[{'address':{'addressCountry':'CA','addressRegion':'ON','addressLocality':'Toronto'}},{'address':{'addressCountry':'CA','addressRegion':'QC','addressLocality':'Gatineau'}}]}
 html='<script type="application/ld+json">'+json.dumps(j)+'</script>'
 r=research.jobs_from_html(html,'https://www.crai.com/fixture','Fixture');assert len(r)==1 and r[0]['city']=='Toronto' and r[0]['deadline'] is None
 j['title']='Economics Intern';j['jobLocation']=j['jobLocation'][1:]
 assert not research.jobs_from_html('<script type="application/ld+json">'+json.dumps(j)+'</script>','https://www.crai.com/fixture','Fixture')
def test_bad_links_and_statuses(client):
 oid=job(client)
 assert client.patch(f'/api/tracking/{oid}',json={'application':'nonsense'}).status_code==400
 assert client.patch(f'/api/tracking/{oid}',json={'resume':'javascript:alert(1)'}).status_code==400
 assert client.post('/api/contacts',json={'name':'Fixture','profile':'file:///etc/passwd'}).status_code==400

def test_greenhouse_feed_and_overlap(client,monkeypatch):
 import fcntl
 from pathlib import Path
 raw={'jobs':[{'id':123,'requisition_id':'test-123','title':'Energy Analyst Intern Summer 2027','location':{'name':'Toronto, Ontario, Canada'},'absolute_url':'https://job-boards.greenhouse.io/test/jobs/123','content':'&lt;p&gt;Undergraduate economics. CA$1,850.00 per week.&lt;/p&gt;','application_deadline':None}]}
 items=research.jobs_from_greenhouse(json.dumps(raw),'Fixture');assert len(items)==1
 assert items[0]['deadline'] is None and items[0]['compensation']=='CA$1,850.00 per week'
 raw['jobs'][0]['location']['name']='London, England, United Kingdom'
 assert not research.jobs_from_greenhouse(json.dumps(raw),'Fixture')
 with open(Path(store.DB).parent/'refresh.lock','w') as handle:
  fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  assert research.refresh() is None
 assert not store.rows('select * from runs')

def test_login_favicon_and_parallel_tabs(client):
 a=client.application.test_client();a.get('/login')
 with a.session_transaction() as s:token=s['login_csrf']
 assert a.get('/favicon.ico').status_code==204
 a.get('/login')
 assert a.post('/login',data={'csrf':token,'password':'test-password-123'}).status_code==302

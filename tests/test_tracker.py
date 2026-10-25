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

def test_broader_internships_and_real_restrictions():
 def feed(title,loc='Toronto',text='Available Summer 2027. Undergraduate economics, finance or analytics student.'):
  return json.dumps({'jobs':[{'id':999,'title':title,'location':{'name':loc},'absolute_url':'https://example.org/fixture','content':text}]})
 stripe=research.jobs_from_greenhouse(feed('Data Analyst, Intern',text='Economics Bachelor’s students graduating in 2028. SQL skills required.'),'Fixture')
 assert stripe[0]['recruiting']=='Dates unclear' and stripe[0]['category']=='Data / business analytics'
 ops=research.jobs_from_greenhouse(feed('Business Systems Intern (Summer 2027)',text='Summer 2027. Must attend a university in Canada. Undergraduate student.'),'Fixture')
 assert ops[0]['authorization']=='Canadian co-op/enrollment restriction'
 assert ops[0]['category']=='Operations / business systems'
 assert not research.jobs_from_greenhouse(feed('Internal Audit Lead'),'Fixture')
 assert not research.jobs_from_greenhouse(feed('PhD Data Scientist Intern'),'Fixture')
 assert not research.jobs_from_greenhouse(feed('Risk Analyst Intern Winter 2027'),'Fixture')
 assert not research.jobs_from_greenhouse(feed('Pricing Intern Summer 2027',loc='Longueuil, Canada'),'Fixture')
 monitor=research.board_monitor(feed('Senior Pricing Analyst'), 'Fixture','https://example.org/board')
 assert monitor[0]['recruiting']=='Monitor' and 'not a verified Summer 2027 internship' in monitor[0]['summary']

def test_lever_adapter_preserves_identity():
 raw=json.dumps([{'id':'fixture-id','text':'Operations Intern Summer 2027','categories':{'location':'Toronto'},'description':'Analyze supply chain data. Summer 2027 undergraduate internship.','lists':[],'hostedUrl':'https://jobs.lever.co/fixture/fixture-id'}])
 jobs=research.jobs_from_greenhouse(research.lever_as_greenhouse(raw),'Fixture')
 assert jobs[0]['requisition']=='fixture-id' and jobs[0]['recruiting']=='Confirmed Summer 2027'

def test_canadian_cities_not_namesakes_in_england():
 assert not research.canadian_cities('Cambridge, Cambridgeshire, England, United Kingdom; London, United Kingdom')
 assert research.canadian_cities('Cambridge, Ontario, Canada')==['Cambridge']
 assert research.canadian_cities('Toronto; Vancouver')==['Toronto','Vancouver']
 assert research.canadian_cities('London, Ontario, Canada')==['London']

def test_deleted_posting_stays_deleted_after_research(client):
 item=fixture_job()
 with store.connect() as c:oid=store.upsert_research(c,item)
 assert client.delete('/api/opportunities/'+str(oid),headers={'X-CSRF-Token':'wrong'}).status_code==403
 assert client.delete('/api/opportunities/'+str(oid)).status_code==200
 assert client.get('/api/data').json['opportunities']==[]
 with store.connect() as c:store.upsert_research(c,item)
 assert client.get('/api/data').json['opportunities']==[]
 backup=client.get('/api/backup').json
 assert backup['tables']['tracking'][0]['deleted']==1
 assert client.post('/api/restore',json=backup).status_code==200
 assert client.get('/api/data').json['opportunities']==[]

def test_recruitment_contacts_priority_and_failed_verification(client,tmp_path,monkeypatch):
 import recruitment
 oid=job(client)
 config=tmp_path/'contacts.json';config.write_text(json.dumps({'Fixture firm':{'sources':['https://example.org/careers'],'approved':[{'name':'Intern recruiting','email':'internships@example.org','type':'internship inbox','source':'https://example.org/careers','scope':'Internship inquiries'}]}}))
 monkeypatch.setattr(recruitment,'CONFIG',config)
 def fetch(url):return '<p>Our internship recruitment team welcomes questions at internships@example.org. '+('Details about student recruiting and applications. '*6)+'</p>'
 assert recruitment.refresh_contacts(fetch)==(1,0)
 d=client.get('/api/data').json['opportunities'][0];assert d['recruitment_contact']=='internships@example.org'
 stamp=json.loads(d['recruitment_contact_details'])['last_verified']
 assert d['last_verified'] is None # Contact verification never verifies the posting.
 recruitment.refresh_contacts(lambda url: (_ for _ in ()).throw(TimeoutError()))
 d=client.get('/api/data').json['opportunities'][0];meta=json.loads(d['recruitment_contact_details'])
 assert d['recruitment_contact']=='internships@example.org' and meta['last_verified']==stamp and meta['status'].startswith('Stale')

def test_recruitment_does_not_repurpose_restricted_emails():
 import recruitment
 assert not recruitment.extract_inboxes('For disability accommodations, email recruitment@example.org.', 'https://example.org/jobs')
 assert not recruitment.extract_inboxes('References must be sent to recruiting@example.org. No other application materials accepted.', 'https://example.org/jobs')
 assert not recruitment.extract_inboxes('Contact privacy@example.org about personal data.', 'https://example.org/jobs')
 assert recruitment.extract_inboxes('Questions about campus recruiting? Contact campus-recruiting@example.org for internship queries.', 'https://example.org/careers')
 assert not recruitment.extract_inboxes('Our recruiter Alex works here. Email formats are firstname.lastname@example.org.', 'https://example.org/careers')

def test_recruitment_fallback_limit_and_inbox_priority(client,tmp_path,monkeypatch):
 import recruitment
 job(client);url='https://example.org/team'
 people=[{'name':f'Fixture recruiter {i}','email':f'person{i}@example.org','type':'recruiter','source':url,'scope':'Verified test fixture'} for i in range(3)]
 path=tmp_path/'sources.json';path.write_text(json.dumps({'Fixture firm':{'sources':[url],'approved':people}}));monkeypatch.setattr(recruitment,'CONFIG',path)
 text='Recruiting team: '+' '.join(p['email'] for p in people)+' '+('Team biographies and recruiting role evidence. '*8)
 recruitment.refresh_contacts(lambda u:text)
 d=client.get('/api/data').json['opportunities'][0];assert len(json.loads(d['recruitment_contact_details'])['contacts'])==2
 inbox={'name':'Intern recruiting','email':'internships@example.org','type':'internship inbox','source':url,'scope':'Internship inquiries'}
 path.write_text(json.dumps({'Fixture firm':{'sources':[url],'approved':people+[inbox]}}));recruitment.refresh_contacts(lambda u:text+' internships@example.org')
 d=client.get('/api/data').json['opportunities'][0];assert d['recruitment_contact']=='internships@example.org'

def test_named_recruiter_needs_explicit_affiliation_and_email():
 import recruitment
 person={'@type':'Person','name':'Fixture recruiter','jobTitle':'Talent Acquisition Partner','email':'fixture@example.org','worksFor':{'name':'Fixture firm'}}
 html='<script type="application/ld+json">'+json.dumps(person)+'</script>'
 assert recruitment.extract_recruiters(html,'https://example.org/team','Fixture firm')[0]['name']=='Fixture recruiter'
 assert not recruitment.extract_recruiters(html,'https://example.org/team','Other firm')
 person.pop('email');html='<script type="application/ld+json">'+json.dumps(person)+'</script>'
 assert not recruitment.extract_recruiters(html,'https://example.org/team','Fixture firm')

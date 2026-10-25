"""Verify public recruiting channels. Never infer addresses or recruiter identities."""
import json,re,html,concurrent.futures
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import store
EMAIL=re.compile(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
CONFIG=Path(__file__).parent/'recruitment_sources.json'
def readable(raw):
 soup=BeautifulSoup(html.unescape(raw),'html.parser')
 for x in soup(['script','style','nav','footer','header']):x.decompose()
 for node in soup.select('[data-cfemail]'):
  try:
   code=bytes.fromhex(node['data-cfemail']);node.replace_with(''.join(chr(b^code[0]) for b in code[1:]))
  except (ValueError,IndexError):pass
 for a in soup.select('a[href^="mailto:"]'):
  address=a['href'][7:].split('?')[0]
  if EMAIL.fullmatch(address):a.append(' '+address)
 return soup.get_text(' ',strip=True).replace('\u200b','').replace('\xa0',' ')
def documents(raw,url):
 if urlparse(url).hostname in ('boards-api.greenhouse.io','api.lever.co'):
  data=json.loads(raw);jobs=data if isinstance(data,list) else data.get('jobs',[data] if 'content' in data else [])
  return [readable(j.get('content','') or j.get('description','')+' '.join(x.get('content','') for x in j.get('lists',[]))+j.get('additional','')) for j in jobs]
 return [readable(raw)]
def extract_inboxes(text,url):
 result=[]
 for m in EMAIL.finditer(text):
  address=m.group();local=address.split('@')[0].lower()
  if not re.search('recruit|career|talent|campus|university',local):continue
  # A public email for accommodation, privacy, references, or reporting scams is
  # not an invitation to send internship expressions of interest.
  context=text[max(0,m.start()-240):m.end()+240]
  if re.search(r'accommodat|disabilit|privacy|reference|scam|fraud|access, correct|delete your information|information security|processes your information|no other application|not accept|do not (?:send|submit)',context,re.I):continue
  if not re.search(r'recruit|hiring|applicant|intern|student|career',context,re.I):continue
  result.append(dict(name='Recruiting inbox',email=address,type='recruiting inbox',source=url,scope='Published recruiting channel. Specific internship, Canadian-office and unsolicited-inquiry coverage is unconfirmed.',evidence=context))
 return result

def refresh_contacts(fetch):
 config=json.loads(CONFIG.read_text());employers=store.rows('SELECT DISTINCT employer FROM opportunities');stamp=store.now()
 def check(row):
  employer=row['employer'];entry=config.get(employer,{'sources':[],'approved':[]});docs=[];failures=[];valid=[]
  for url in entry['sources']:
   try:
    text=fetch(url);documents_=documents(text,url)
    if not documents_ or not any(len(t)>150 for t in documents_):raise ValueError('Insufficient content')
    if any(re.search(r'verify you are human|just a moment|access denied',t,re.I) for t in documents_):raise ValueError('Access challenge')
    docs.append(url)
    for c in entry.get('approved',[]):
     if c['source']==url and any(c['email'].lower() in t.lower() for t in documents_):valid.append(c)
    if not valid:
     for t in documents_:valid.extend(extract_inboxes(t,url))
   except Exception:failures.append(url)
  # Prefer an approved internship inbox. Recruiter fallback must be individually
  # evidenced with a published work address and role; never fabricated from names.
  valid=list({c['email'].lower():c for c in valid if c['email'].lower() not in entry.get('excluded',[])}.values())
  preferred=[c for c in valid if c['type']=='internship inbox'];inboxes=[c for c in valid if c['type']!='recruiter']
  chosen=preferred[:1] or inboxes[:1] or [c for c in valid if c['type']=='recruiter'][:2]
  details=dict(status='Published recruiting contact' if chosen else 'Research incomplete — blocked sources' if failures else 'No public recruiting email verified' if entry['sources'] else 'Not researched — company sources not configured',contacts=chosen,sources_checked=docs,failed_sources=failures,last_attempted=stamp,last_verified=stamp if chosen else None,notes=entry.get('notes','')+' Named recruiter fallback with public work email not verified.' if not chosen else entry.get('notes',''))
  return employer,details
 results=list(concurrent.futures.ThreadPoolExecutor(5).map(check,employers))
 with store.connect() as c:
  for employer,details in results:
   for old in c.execute('SELECT id,recruitment_contact,recruitment_contact_details FROM opportunities WHERE employer=?',(employer,)).fetchall():
    value='; '.join(x['email'] for x in details['contacts'])
    current=dict(details)
    if not value and old['recruitment_contact']:
     try:previous=json.loads(old['recruitment_contact_details']);current['contacts']=previous.get('contacts',[]);current['last_verified']=previous.get('last_verified')
     except ValueError:pass
     current['status']='Stale — recruiting contact not reverified';value=old['recruitment_contact']
    if value!=old['recruitment_contact']:c.execute('INSERT INTO changes(opportunity_id,at,field,previous,current) VALUES(?,?,?,?,?)',(old['id'],stamp,'recruitment_contact',old['recruitment_contact'],value))
    c.execute('UPDATE opportunities SET recruitment_contact=?,recruitment_contact_details=? WHERE id=?',(value,json.dumps(current,ensure_ascii=False),old['id']))
 return sum(bool(d['contacts']) for _,d in results),sum(bool(d['failed_sources']) for _,d in results)

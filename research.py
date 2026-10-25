"""Bounded official-source discovery. No generative claims or inferred authorization."""
import json,re,hashlib,time,fcntl,html as html_module
from pathlib import Path
from urllib.parse import urlparse,urljoin
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import store
CITIES=['Toronto','Ottawa','Vancouver','Calgary','Edmonton','Winnipeg','Halifax','Hamilton','Kitchener','Waterloo','London','Victoria','Saskatoon','Regina','Fredericton','Moncton',"St. John"]
HEADERS={'User-Agent':'InternshipTracker/1.0 (personal research; weekly checks)'}
def fetch(url):
 # Only public HTTPS source hosts approved in code. Redirects must remain on that list.
 allowed={'www.analysisgroup.com','www.nera.com','www.crai.com','www.compasslexecon.com','www.brattle.com','www.bankofcanada.ca','www.canada.ca','boards-api.greenhouse.io','api.lever.co'}
 for _ in range(5):
  p=urlparse(url)
  if p.scheme!='https' or p.hostname not in allowed or p.username or p.port not in (None,443):raise ValueError('Source host is not approved')
  with requests.get(url,headers=HEADERS,timeout=(8,22),allow_redirects=False,stream=True) as r:
   if r.is_redirect:url=urljoin(url,r.headers['Location']);continue
   r.raise_for_status();chunks=[];size=0
   for chunk in r.iter_content(65536):
    size+=len(chunk)
    if size>3_000_000:raise ValueError('Source exceeds 3 MB limit')
    chunks.append(chunk)
   return b''.join(chunks).decode(r.encoding or 'utf-8',errors='replace')
 raise ValueError('Too many redirects')
def jobs_from_html(html,url,employer):
 soup=BeautifulSoup(html,'html.parser'); jobs=[]
 def walk(o):
  if isinstance(o,list):
   for v in o:walk(v)
  elif isinstance(o,dict):
   if o.get('@type')=='JobPosting':jobs.append(o)
   for k,v in o.items():
    if isinstance(v,(dict,list)):walk(v)
 for script in soup.find_all('script',type='application/ld+json'):
  try:walk(json.loads(script.string or script.get_text()))
  except (ValueError,TypeError):pass
 result=[]
 for j in jobs:
  title=j.get('title','');desc=BeautifulSoup(j.get('description',''),'html.parser').get_text(' ',strip=True)
  if not re.search(r'intern|student|stagiaire|stage',title,re.I):continue
  locations=j.get('jobLocation',[]);locations=locations if isinstance(locations,list) else [locations];cities=[]
  for loc in locations:
   a=loc.get('address',{})
   if not isinstance(a,dict):continue
   city=a.get('addressLocality','');country=a.get('addressCountry','');region=a.get('addressRegion','')
   if isinstance(country,dict):country=country.get('name','')
   if country.lower() in ('ca','canada') and region.lower() not in ('qc','quebec','québec') and any(x.lower() in city.lower() for x in CITIES):cities.append(city)
  if not cities:continue # Remote permissions and ambiguous geography require manual verification.
  if not re.search(r'econom|analys|research|consult|data|recherche',title+' '+desc,re.I):continue
  confirmed=bool(re.search(r'(summer|été)\s*2027|2027\s*(summer|été)',title+' '+desc,re.I))
  deadline=j.get('applicationDeadline');deadline=deadline[:10] if isinstance(deadline,str) and re.match(r'^\d{4}-\d{2}-\d{2}',deadline) else None
  published=j.get('datePosted');published=published[:10] if isinstance(published,str) and re.match(r'^\d{4}-\d{2}-\d{2}',published) else None
  recruiting='Confirmed Summer 2027' if confirmed else 'Dates unclear'
  if deadline and deadline<datetime.now().date().isoformat():recruiting='Closed / archived'
  result.append(dict(employer=employer,role=title,city=', '.join(sorted(set(cities))),url=j.get('url') or url,requisition=str(j.get('identifier',{}).get('value','')) if isinstance(j.get('identifier'),dict) else '',cycle='2027' if confirmed else 'unclear',recruiting=recruiting,deadline=deadline,published_date=published,summary=desc[:3500],evidence=json.dumps(j,ensure_ascii=False)[:15000],requirements='Review official posting; automated extraction does not establish eligibility.',outside_quebec='Confirmed listed offices',authorization='Needs clarification',fit='Potential fit for economics research, econometrics and analytical experience; review degree requirements.'))
 return result

def jobs_from_greenhouse(raw,employer):
 data=json.loads(raw);result=[]
 for job in data.get('jobs', [data] if 'title' in data else []):
  location=job.get('location',{}).get('name','')
  if not re.search(r'Canada',location,re.I) or re.search(r'Quebec|Québec|Montreal|Montréal|Gatineau',location,re.I):continue
  city=next((x for x in CITIES if re.search(r'\b'+re.escape(x)+r'\b',location,re.I)),None)
  if not city:continue
  desc=BeautifulSoup(html_module.unescape(job.get('content','')),'html.parser').get_text(' ',strip=True)
  schema={'@type':'JobPosting','title':job['title'],'description':desc,'url':job['absolute_url'],'identifier':{'value':str(job.get('requisition_id') or job['id'])},'jobLocation':{'address':{'addressCountry':'CA','addressLocality':city,'addressRegion':'outside QC'}},'applicationDeadline':job.get('application_deadline'),'datePosted':job.get('first_published')}
  parsed=jobs_from_html('<script type="application/ld+json">'+json.dumps(schema)+'</script>',job['absolute_url'],employer)
  for item in parsed:
   item['requirements']=desc
   item['evidence']=json.dumps(job,ensure_ascii=False)[:20000]
   salary=re.search(r'CA\$[\d,]+(?:\.\d+)? per week',desc)
   if salary:item['compensation']=salary.group()
   item['fit']='Quantitative economics, Stata/R and research responsibilities align with your panel-data work. Check climate/energy coursework and academic requirements.'
   item['summary']=desc[:1600]
   item['authorization']='Employer support unknown'
   if re.search(r'must (?:already )?(?:be |have )?(?:authorized|eligible|authorization) to work in Canada',desc,re.I):item['authorization']='Existing Canadian work authorization required'
  result.extend(parsed)
 return result

def refresh():
 lock=Path(store.DB).parent/'refresh.lock';lock.parent.mkdir(parents=True,exist_ok=True)
 with open(lock,'w') as handle:
  try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return None
  stamp=store.now()
  with store.connect() as c:
   c.execute("UPDATE runs SET status='Interrupted',finished=? WHERE status='Running'",(stamp,))
   rid=c.execute("INSERT INTO runs(started,status) VALUES(?,'Running')",(stamp,)).lastrowid
  failures=0;checked=0;discovered=0
  for source in store.rows('SELECT * FROM sources'):
   try:
    html=fetch(source['url']);soup=BeautifulSoup(html,'html.parser')
    # Challenge pages must never count as verification.
    if re.search(r'verify you are human|access denied|just a moment|captcha',soup.get_text(' ',strip=True),re.I):raise ValueError('Access challenge; not verified')
    for x in soup(['script','style','nav','footer','header']):x.decompose()
    excerpt=soup.get_text(' ',strip=True)[:40000]
    if len(excerpt)<150:raise ValueError('Insufficient readable source content')
    fingerprint=hashlib.sha256(excerpt.encode()).hexdigest()
    candidates=jobs_from_greenhouse(html,source['employer']) if source['kind']=='greenhouse' else jobs_from_html(html,source['url'],source['employer'])
    # Discover bounded official links from career index pages, plus tracked postings.
    links=[]
    if source['kind']=='page' and 'canada.ca' not in source['url']:
     root=BeautifulSoup(html,'html.parser')
     for a in root.find_all('a',href=True):
      u=urljoin(source['url'],a['href']).split('#')[0]
      if urlparse(u).hostname==urlparse(source['url']).hostname and re.search(r'intern|student|stagiaire',a.get_text(' ',strip=True),re.I) and u not in links and u!=source['url']:links.append(u)
    for u in links[:8]:
     try:candidates+=jobs_from_html(fetch(u),u,source['employer'])
     except Exception:failures+=1
    with store.connect() as c:
     for item in candidates:store.upsert_research(c,item);discovered+=1
     if source['digest'] and source['digest']!=fingerprint:c.execute('INSERT INTO changes(at,field,previous,current) VALUES(?,?,?,?)',(store.now(),'source content',source['name']+' changed',source['url']))
     c.execute('UPDATE sources SET attempted=?,verified=?,error=NULL,excerpt=?,digest=? WHERE id=?',(store.now(),store.now(),excerpt,fingerprint,source['id']))
    checked+=1
   except Exception as e:
    failures+=1
    with store.connect() as c:c.execute('UPDATE sources SET attempted=?,error=? WHERE id=?',(store.now(),str(e)[:800],source['id']))
  # Recheck actual postings independently. Failed checks preserve last verified data.
  for job in store.rows("SELECT * FROM opportunities WHERE recruiting!='Monitor' AND url!=''"):
   try:
    gh=re.search(r'job-boards.greenhouse.io/([^/]+)/jobs/(\d+)',job['url'])
    candidates=jobs_from_greenhouse(fetch(f'https://boards-api.greenhouse.io/v1/boards/{gh[1]}/jobs/{gh[2]}'),job['employer']) if gh else jobs_from_html(fetch(job['url']),job['url'],job['employer'])
    matching=[x for x in candidates if x['url']==job['url'] and x['cycle']==job['cycle']]
    if not matching:raise ValueError('No matching structured posting; manual review needed. Not marked closed.')
    with store.connect() as c:store.upsert_research(c,matching[0])
   except Exception as e:
    failures+=1
    with store.connect() as c:c.execute('INSERT INTO changes(opportunity_id,at,field,current) VALUES(?,?,?,?)',(job['id'],store.now(),'verification failed',str(e)[:500]))
  with store.connect() as c:c.execute('UPDATE runs SET finished=?,status=?,summary=? WHERE id=?',(store.now(),'Partial' if failures else 'Complete',f'{checked} sources verified; {discovered} posting observations; {failures} failed checks. Coverage is bounded; JS-only boards and contacts require manual research.',rid))
  return rid

def worker():
 store.init()
 while True:
  now=datetime.now(ZoneInfo('America/New_York'))
  monday=(now-timedelta(days=now.weekday())).replace(hour=9,minute=0,second=0,microsecond=0)
  if now>=monday:
   with store.connect() as c:
    c.execute('BEGIN IMMEDIATE');last=c.execute("SELECT value FROM settings WHERE key='last_scheduled_week'").fetchone()
    if not last or last[0]!=monday.date().isoformat():due=True
    else:due=False
   if due:
    if refresh() is not None:
     with store.connect() as c:c.execute("INSERT OR REPLACE INTO settings VALUES('last_scheduled_week',?)",(monday.date().isoformat(),))
  with store.connect() as c:c.execute("INSERT OR REPLACE INTO settings VALUES('worker_heartbeat',?)",(store.now(),))
  time.sleep(30)
if __name__=='__main__':
 import sys
 store.init()
 if '--once' in sys.argv:print(refresh())
 else:worker()

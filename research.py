"""Bounded official-source discovery. No generative claims or inferred authorization."""
import json,re,hashlib,time,fcntl,html as html_module
from pathlib import Path
from urllib.parse import urlparse,urljoin
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import store
CITIES=['Mississauga','Markham','Burnaby','Richmond','Oakville','Burlington','Cambridge','Guelph','Toronto','Ottawa','Vancouver','Calgary','Edmonton','Winnipeg','Halifax','Hamilton','Kitchener','Waterloo','London','Victoria','Saskatoon','Regina','Fredericton','Moncton',"St. John"]
HEADERS={'User-Agent':'InternshipTracker/1.0 (personal research; weekly checks)'}
def fetch(url):
 # Only public HTTPS source hosts approved in code. Redirects must remain on that list.
 contact_hosts={urlparse(url).hostname for entry in json.loads((Path(__file__).parent/'recruitment_sources.json').read_text()).values() for url in entry['sources']}
 allowed=contact_hosts | {'www.analysisgroup.com','www.nera.com','www.crai.com','www.compasslexecon.com','www.brattle.com','www.bankofcanada.ca','www.canada.ca','boards-api.greenhouse.io','api.lever.co'}
 for _ in range(5):
  p=urlparse(url)
  if p.scheme!='https' or p.hostname not in allowed or p.username or p.port not in (None,443):raise ValueError('Source host is not approved')
  with requests.get(url,headers=HEADERS,timeout=(8,22),allow_redirects=False,stream=True) as r:
   if r.is_redirect:url=urljoin(url,r.headers['Location']);continue
   r.raise_for_status();chunks=[];size=0
   for chunk in r.iter_content(65536):
    size+=len(chunk)
    if size>16_000_000:raise ValueError('Source exceeds 16 MB limit')
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
  if not re.search(r'\bintern(?:ship)?\b|\bstudent\b|co[ -]?op|stagiaire|\bstage\b',title,re.I):continue
  locations=j.get('jobLocation',[]);locations=locations if isinstance(locations,list) else [locations];cities=[]
  for loc in locations:
   a=loc.get('address',{})
   if not isinstance(a,dict):continue
   city=a.get('addressLocality','');country=a.get('addressCountry','');region=a.get('addressRegion','')
   if isinstance(country,dict):country=country.get('name','')
   if country.lower() in ('ca','canada') and region.lower() not in ('qc','quebec','québec') and any(x.lower() in city.lower() for x in CITIES):cities.append(city)
  if not cities:continue # Remote permissions and ambiguous geography require manual verification.
  if not re.search(r'econom|analys|research|consult|data|recherche|pricing|operations|business|finance|strategy|investment|risk|supply',title+' '+desc,re.I):continue
  confirmed=bool(re.search(r'(summer|été)\s*2027|2027\s*(summer|été)',title+' '+desc,re.I))
  deadline=j.get('applicationDeadline');deadline=deadline[:10] if isinstance(deadline,str) and re.match(r'^\d{4}-\d{2}-\d{2}',deadline) else None
  published=j.get('datePosted');published=published[:10] if isinstance(published,str) and re.match(r'^\d{4}-\d{2}-\d{2}',published) else None
  recruiting='Confirmed Summer 2027' if confirmed else 'Dates unclear'
  if deadline and deadline<datetime.now().date().isoformat():recruiting='Closed / archived'
  result.append(dict(employer=employer,role=title,city=', '.join(sorted(set(cities))),url=j.get('url') or url,requisition=str(j.get('identifier',{}).get('value','')) if isinstance(j.get('identifier'),dict) else '',cycle='2027' if confirmed else 'unclear',recruiting=recruiting,deadline=deadline,published_date=published,summary=desc[:3500],evidence=json.dumps(j,ensure_ascii=False)[:15000],requirements='Review official posting; automated extraction does not establish eligibility.',outside_quebec='Confirmed listed offices',authorization='Needs clarification',fit='Potential fit for economics research, econometrics and analytical experience; review degree requirements.'))
 return result

def canadian_cities(location):
 result=[]
 for segment in location.split(';'):
  canadian=bool(re.search(r'Canada|Ontario|British Columbia|Alberta|Manitoba|Saskatchewan|Nova Scotia|New Brunswick|Newfoundland|\bON\b|\bBC\b',segment,re.I))
  if re.search(r'United Kingdom|England|United States|\bUSA\b|Australia',segment,re.I) and not canadian:continue
  for city in CITIES:
   if re.search(r'\b'+re.escape(city)+r'\b',segment,re.I) and (city not in {'London','Cambridge','Richmond','Victoria','Burlington','Hamilton'} or canadian):result.append(city)
 return sorted(set(result))

def jobs_from_greenhouse(raw,employer):
 data=json.loads(raw);result=[]
 for job in data.get('jobs', [data] if 'title' in data else []):
  location=job.get('location',{}).get('name','')
  if re.search(r'Quebec|Québec|Montreal|Montréal|Gatineau|Longueuil',location,re.I):continue
  if not re.search(r'Canada|\bCA\b|Mississauga|Markham|Burnaby|Richmond|Oakville|Burlington|Cambridge|Guelph|Toronto|Vancouver|Ottawa|Calgary|Waterloo|Kitchener|Edmonton|Winnipeg|Halifax|Hamilton',location,re.I):continue
  cities=canadian_cities(location)
  if not cities:continue
  city=cities[0]
  desc=BeautifulSoup(html_module.unescape(job.get('content','')),'html.parser').get_text(' ',strip=True)
  if re.search(r'\bPhD\b|doctoral|graduate co.op',job['title'],re.I):continue
  if not re.search(r'econom|analys|research|pricing|operations|business|finance|strategy|investment|risk|supply',job['title'],re.I):continue
  if re.search(r'(winter|fall|spring)\s*202[67]',job['title'],re.I) and not re.search(r'summer\s*2027',job['title'],re.I):continue
  schema={'@type':'JobPosting','title':job['title'],'description':desc,'url':job['absolute_url'],'identifier':{'value':str(job.get('requisition_id') or job['id'])},'jobLocation':{'address':{'addressCountry':'CA','addressLocality':city,'addressRegion':'outside QC'}},'applicationDeadline':job.get('application_deadline'),'datePosted':job.get('first_published')}
  parsed=jobs_from_html('<script type="application/ld+json">'+json.dumps(schema)+'</script>',job['absolute_url'],employer)
  for item in parsed:
   item['requirements']=desc
   item['evidence']=json.dumps({k:(v[:10000] if k=='content' else v) for k,v in job.items()},ensure_ascii=False)
   salary=re.search(r'CA\$[\d,]+(?:\.\d+)? per week',desc)
   if salary:item['compensation']=salary.group()
   item['city']=', '.join(cities)
   item['category']=category(job['title'])
   item['fit']='Economics, research, Stata/R and analytical project experience may transfer well. Review the stated degree, technical skills and enrollment requirements.'
   item['summary']=desc[:1600]
   item['authorization']='Employer support unknown'
   if re.search(r'must (?:already )?(?:be |have )?(?:authorized|eligible|authorization) to work in Canada',desc,re.I):item['authorization']='Existing Canadian work authorization required'
   if re.search(r'(?:university|institution|school) in Canada|Canadian (?:university|college|institution)',desc,re.I):item['authorization']='Canadian co-op/enrollment restriction'
   pay=re.search(r'(?:expected|anticipated|base).{0,180}(?:CAD|CA\$).{0,100}(?:hour|week|month|year)',desc,re.I)
   if pay:item['compensation']=pay.group()
   if item['recruiting']=='Confirmed Summer 2027':item['dates']='Summer 2027; exact start/end dates not extracted. See source.'
   if re.search(r'Jan\s*-\s*Dec\s*2027',job['title'],re.I):
    item['dates']='January–December 2027 (12 months; not a summer-only placement)'
    item['fit']='Analytical operations work, but the published 12-month term may conflict with your university schedule. Ask whether a summer-only term is possible.'
  result.extend(parsed)
 return result

def lever_as_greenhouse(raw):
 jobs=[]
 for j in json.loads(raw):
  body=j.get('description','')+' '.join(x.get('content','') for x in j.get('lists',[])) + j.get('additional','')
  jobs.append({'id':j['id'],'requisition_id':j['id'],'title':j['text'],'location':{'name':j.get('categories',{}).get('location','')},'content':body,'absolute_url':j['hostedUrl']})
 return json.dumps({'jobs':jobs})

def category(title):
 for pattern,label in [(r'pricing','Pricing / revenue'),(r'operations|supply|systems','Operations / business systems'),(r'data|analytics','Data / business analytics'),(r'finance|investment|risk','Finance / risk analytics'),(r'UX|user experience','Product / UX research'),(r'econom','Economic consulting'),(r'business|strategy','Business / strategy'),(r'research','Research')]:
  if re.search(pattern,title,re.I):return label
 return 'Business / data analysis'

def board_monitor(raw,employer,url):
 jobs=json.loads(raw).get('jobs',[]);eligible=[]
 for j in jobs:
  loc=j.get('location',{}).get('name','')
  if canadian_cities(loc) and not re.search(r'Montreal|Montréal|Quebec|Québec|Gatineau',loc,re.I) and re.search(r'analys|data|research|pricing|operations|business|finance|strategy|risk|investment|supply',j['title'],re.I):eligible.append(j)
 if not eligible:return []
 examples=[{'title':j['title'],'location':j['location']['name'],'url':j['absolute_url']} for j in eligible[:6]]
 cities=sorted({city for j in eligible for city in canadian_cities(j['location']['name'])})
 return [dict(employer=employer,role='Canadian analytical hiring · monitor internships',city=', '.join(cities),url=url,cycle='2027',recruiting='Monitor',category='Employer watchlist',summary='Employer has current Canadian analytical hiring. This entry is a research target, not a verified Summer 2027 internship or a claim of an undergraduate internship program. Example current job titles: '+ '; '.join(j['title'] for j in eligible[:3]),requirements='Internship dates, undergraduate eligibility, Canadian enrollment and work authorization must be verified in a specific posting. Example roles in the evidence may be experienced full-time positions.',fit='Monitor for undergraduate data, operations, pricing, business and economics-related internships.',evidence=json.dumps(examples,ensure_ascii=False),outside_quebec='Listed Canadian offices outside Quebec; internship work location unconfirmed',authorization='Employer support unknown')]

def refresh():
 lock=Path(store.DB).parent/'refresh.lock';lock.parent.mkdir(parents=True,exist_ok=True)
 with open(lock,'w') as handle:
  try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return None
  stamp=store.now()
  with store.connect() as c:
   c.execute("UPDATE runs SET status='Interrupted',finished=? WHERE status='Running'",(stamp,))
   rid=c.execute("INSERT INTO runs(started,status) VALUES(?,'Running')",(stamp,)).lastrowid
  failures=0;checked=0;discovered=0;observed_urls=set()
  for source in store.rows('SELECT * FROM sources'):
   try:
    html=fetch(source['url']);soup=BeautifulSoup(html,'html.parser')
    # Challenge pages must never count as verification.
    if re.search(r'verify you are human|access denied|just a moment|captcha',soup.get_text(' ',strip=True),re.I):raise ValueError('Access challenge; not verified')
    for x in soup(['script','style','nav','footer','header']):x.decompose()
    excerpt=soup.get_text(' ',strip=True)[:40000]
    if len(excerpt)<150:raise ValueError('Insufficient readable source content')
    fingerprint=hashlib.sha256(excerpt.encode()).hexdigest()
    board_data=lever_as_greenhouse(html) if source['kind']=='lever' else html
    candidates=jobs_from_greenhouse(board_data,source['employer']) if source['kind'] in ('greenhouse','lever') else jobs_from_html(html,source['url'],source['employer'])
    if source['kind'] in ('greenhouse','lever') and source['employer'] not in ('Brattle','CRA'):candidates+=board_monitor(board_data,source['employer'],source['url'])
    observed_urls.update(x['url'] for x in candidates)
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
   if job['url'] in observed_urls:continue
   try:
    gh=re.search(r'job-boards.greenhouse.io/([^/]+)/jobs/(\d+)',job['url'])
    candidates=jobs_from_greenhouse(fetch(f'https://boards-api.greenhouse.io/v1/boards/{gh[1]}/jobs/{gh[2]}'),job['employer']) if gh else jobs_from_html(fetch(job['url']),job['url'],job['employer'])
    matching=[x for x in candidates if x['url']==job['url'] and x['cycle']==job['cycle']]
    if not matching:raise ValueError('No matching structured posting; manual review needed. Not marked closed.')
    with store.connect() as c:store.upsert_research(c,matching[0])
   except Exception as e:
    failures+=1
    with store.connect() as c:c.execute('INSERT INTO changes(opportunity_id,at,field,current) VALUES(?,?,?,?)',(job['id'],store.now(),'verification failed',str(e)[:500]))
  import recruitment
  contact_count,contact_gaps=recruitment.refresh_contacts(fetch)
  with store.connect() as c:c.execute('UPDATE runs SET finished=?,status=?,summary=? WHERE id=?',(store.now(),'Partial' if failures or contact_gaps else 'Complete',f'{checked} sources verified; {discovered} posting observations; {failures} failed posting checks; recruiting contacts verified for {contact_count} employers, {contact_gaps} employer contact checks incomplete. Coverage is bounded; JS-only boards and contacts require manual research.',rid))
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

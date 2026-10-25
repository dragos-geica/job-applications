"""Verified program watchlist. Rerunnable; never seeds fictional openings or people."""
from bs4 import BeautifulSoup
import store,research
PROGRAMS=[dict(employer='Analysis Group',role='Summer analyst intern · program to monitor',url='https://www.analysisgroup.com/careers/career-path/summer-analyst-intern/',category='Economic consulting',summary='Entry-level summer analyst program involving economic and business analysis, case teams, litigation and regulatory matters. This is a general program description, not a verified Canadian Summer 2027 vacancy.',requirements='Generalist program seeks rising seniors and first-year master’s students in economics and related quantitative subjects. Specific posting, office, Canadian work authorization and enrollment restrictions must be checked.',fit='Strong match to economics research, Stata/R, panel data and consulting experience. A 2028 graduation would ordinarily make Summer 2027 the summer before senior year; confirm the actual posting.',dates='Summer program; specific 2027 dates not published.'),dict(employer='Bank of Canada',role='Student work program · monitor undergraduate postings',url='https://www.bankofcanada.ca/careers/students/',category='Economic research / policy',summary='Student positions are typically four-month terms. The general program page says summer terms run May–August, with applications opening in January. This is a general recruiting pattern, not a 2027 opening or deadline.',requirements='Student program welcomes college and university students. Co-op students must confirm placement requirements with their school. Master’s and PhD internships are separate programs and do not match an undergraduate profile.',fit='Relevant to economics research and substantive data work. Office, role duties, enrollment and work authorization need verification in each posting.',dates='General summer term: May–August; 2027 dates unconfirmed.')]
def seed():
 store.init()
 with store.connect() as c:
  c.execute("UPDATE sources SET url='https://www.nera.com/why-nera.html' WHERE name='NERA'")
  c.execute("UPDATE sources SET url='https://www.canada.ca/en/immigration-refugees-citizenship/services/work-canada/hire-temporary-foreign/french-speaking-bilingual-workers-outside-quebec/hire.html' WHERE name='IRCC Francophone Mobility'")
 with store.connect() as c:
  for board,firm in [('thebrattlegroup','Brattle'),('charlesriverassociates','CRA')]:
   c.execute('INSERT OR IGNORE INTO sources(name,url,employer,kind) VALUES(?,?,?,?)',(firm+' official Greenhouse board',f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true',firm,'greenhouse'))
 for p in PROGRAMS:
  try:
   html=research.fetch(p['url']);s=BeautifulSoup(html,'html.parser');[x.decompose() for x in s(['script','style','nav','header','footer'])];text=s.get_text(' ',strip=True)
   if len(text)<500:raise ValueError('Insufficient evidence')
   with store.connect() as c:
    c.execute('INSERT OR IGNORE INTO sources(name,url,employer,kind) VALUES(?,?,?,?)',(p['employer']+' student program',p['url'],p['employer'],'program'))
    item={**p,'recruiting':'Monitor','cycle':'2027','city':'','evidence':text[:18000],'authorization':'Employer support unknown'}
    store.upsert_research(c,item)
  except Exception as e:print(p['employer'],'not seeded:',e)
if __name__=='__main__':seed()

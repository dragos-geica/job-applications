"""Run explicitly with .venv/bin/python tests/browser_smoke.py; isolated test data."""
import sys,os,tempfile,subprocess,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from werkzeug.security import generate_password_hash
from playwright.sync_api import sync_playwright
import store
with tempfile.TemporaryDirectory() as t:
 store.DB=str(Path(t)/'test.sqlite3');store.init();Path(t,'password.hash').write_text(generate_password_hash('browser-fixture-password'))
 with store.connect() as c:
  for employer,city,deadline in [('Fixture Alpha','Toronto','2027-01-30'),('Fixture Beta','Ottawa','2027-01-02')]:
   store.upsert_research(c,dict(employer=employer,role='Research Intern Summer 2027',city=city,url='https://example.org/'+city,cycle='2027',recruiting='Confirmed Summer 2027',deadline=deadline))
 env={**os.environ,'DATABASE_PATH':store.DB,'PORT':'8012'}
 server=subprocess.Popen([sys.executable,'app.py'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  time.sleep(1)
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
   page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto('http://127.0.0.1:8012');page.locator('[name=password]').fill('browser-fixture-password');page.get_by_role('button',name='Sign in',exact=True).click();page.wait_for_selector('table',timeout=4000)
   page.locator('[data-filter=city]').select_option('Ottawa');assert page.locator('tbody tr').count()==1
   page.locator('[data-filter=city]').select_option('');page.locator('#sort').select_option('deadline');assert 'Fixture Beta' in page.locator('tbody tr').first.inner_text()
   page.locator('[data-job]').first.click();page.locator('[name=notes]').fill('Browser persistent note');page.locator('[name=saved]').check();page.get_by_role('button',name='Save tracking',exact=True).click();page.wait_for_timeout(300);page.locator('#close').click();page.reload();page.wait_for_selector('table');page.locator('[data-job]').filter(has_text='Fixture Beta').click();assert page.locator('[name=notes]').input_value()=='Browser persistent note';page.locator('#close').click()
   page.locator('[data-view=contacts]').first.click();page.locator('#add').click();page.locator('[name=name]').fill('Browser contact fixture');page.get_by_role('button',name='Save contact',exact=True).click();page.wait_for_selector('#interaction-form');page.locator('[name=notes]').fill('Contact fixture interaction');page.locator('[name=followup]').fill('2027-01-01');page.get_by_role('button',name='Save interaction',exact=True).click();page.wait_for_timeout(300);assert 'Contact fixture interaction' in page.locator('#detail').inner_text();page.locator('#close').click()
   page.locator('[data-view=applications]').click();page.get_by_role('button',name='Kanban view').click();page.wait_for_selector('.kanban')
   page.locator('[data-view=week]').click();assert page.locator('h1').inner_text()=='This week'
   page.locator('[data-view=settings]').click();page.wait_for_selector('#permit-form');assert page.locator('#restore-form').is_visible()
   page.locator('[data-view=opportunities]').click();page.screenshot(path='/tmp/northbound-desktop.png',full_page=True)
   page.set_viewport_size({'width':390,'height':844});page.screenshot(path='/tmp/northbound-mobile.png',full_page=True)
   assert not errors,errors
   browser.close();print('Browser smoke passed: login, filters, sorting, persisted edits, contact interaction, Kanban, digest, settings, mobile; no JS errors.')
 finally:server.terminate();server.wait(timeout=10)

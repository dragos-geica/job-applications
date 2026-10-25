"""Run after export_pages.py; uses an isolated browser profile, never user storage."""
import subprocess,sys,time
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
server=subprocess.Popen([sys.executable,'-m','http.server','8031','--bind','127.0.0.1','--directory',str(root/'_site')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try:
 time.sleep(.5)
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=b.new_page();page.goto('http://127.0.0.1:8031');page.wait_for_selector('table')
  data=page.evaluate("pagesAPI('data')");job=next(j for j in data['opportunities'] if j['employer']=='Lyft' and 'Business Systems' in j['role'])
  page.locator(f'[data-job="{job["id"]}"]').first.click()
  page.once('dialog',lambda d:d.dismiss());page.get_by_role('button',name='Delete posting',exact=True).click()
  assert page.locator('#panel').is_visible()
  page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='Delete posting',exact=True).click()
  page.wait_for_selector('#panel',state='hidden')
  page.reload();page.wait_for_selector('table');page.evaluate("pagesAPI('refresh','POST',{})")
  assert all(j['id']!=job['id'] for j in page.evaluate("pagesAPI('data')")['opportunities'])
  page.locator('[data-view=settings]').click()
  with page.expect_download() as downloaded:page.get_by_text('Download JSON backup',exact=True).click()
  import json
  backup=json.loads(downloaded.value.path().read_text());assert backup['state']['tracking'][str(job['id'])]['deleted']
  second=b.new_page();second.goto('http://127.0.0.1:8031');second.wait_for_selector('table')
  second.evaluate('(backup)=>pagesAPI("restore","POST",backup)',backup)
  assert all(j['id']!=job['id'] for j in second.evaluate("pagesAPI('data')")['opportunities'])
  b.close();print('Delete confirmation, reload/refresh persistence, and backup/restore passed.')
finally:server.terminate();server.wait(timeout=10)

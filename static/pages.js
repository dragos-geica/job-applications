'use strict';
// The only personal storage is IndexedDB in this browser. No personal requests are sent.
window.NORTHBOUND_PAGES=true;
const pagesDB=new Promise((resolve,reject)=>{const r=indexedDB.open('northbound-private-tracking',1);r.onupgradeneeded=()=>r.result.createObjectStore('state');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('Browser storage is unavailable. Enable site storage to save tracking.'));});
let publicResearch;
const trackingDefaults={application:'Saved',outreach:'Not started',priority:3,notes:'',next_action:'',due:null,applied_date:null,interview_date:null,resume:'',cover_letter:'',saved:0};
const enums={application:['Saved','Preparing','Applied','Interviewing','Offer','Rejected','Withdrawn'],outreach:['Not started','Contact identified','Contacted','Replied','Call scheduled','Follow-up due','Complete'],recruiting:['Confirmed Summer 2027','Dates unclear','Monitor','Closed / archived'],authorization:['Employer support unknown','Employer support confirmed','Existing Canadian work authorization required','Canadian co-op/enrollment restriction','Citizenship, residency, or clearance restriction','Needs clarification']};
async function getResearch(force=false){if(force||!publicResearch){const r=await fetch('./research.json',{cache:'no-store'});if(!r.ok)throw Error('Published research unavailable. Your saved data is still in this browser.');publicResearch=await r.json();}return publicResearch;}
function emptyState(){return {manual:[],edits:{},tracking:{},contacts:[],interactions:[],contact_opportunities:[],settings:{},nextId:-1};}
async function stateOperation(write,fn){const db=await pagesDB;return new Promise((resolve,reject)=>{const t=db.transaction('state',write?'readwrite':'readonly'),s=t.objectStore('state'),r=s.get('personal');let result;r.onsuccess=()=>{try{const state=r.result||emptyState();result=fn(state);if(write)s.put(state,'personal');}catch(e){reject(e);t.abort();}};t.oncomplete=()=>resolve(result);t.onerror=()=>reject(Error('Could not save browser data; export a backup and check available storage.'));});}
function combined(s,research){return {...research,opportunities:[...research.opportunities,...s.manual].map(j=>({...j,...s.edits[j.id],...trackingDefaults,...s.tracking[j.id],opportunity_id:j.id})),contacts:s.contacts,interactions:s.interactions,contact_opportunities:s.contact_opportunities,settings:s.settings,enums,worker_active:false,pages:true};}
async function saveDownload(name,content,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([content],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
window.pagesAPI=async function(path,method='GET',data){
 const research=await getResearch();
 if(path==='data')return stateOperation(false,s=>combined(s,research));
 if(path==='refresh'){await getResearch(true);return {ok:true};}
 if(path==='logout')return {ok:true};
 if(path==='restore')return stateOperation(true,s=>{
  let replacement;
  if(data?.format==='northbound-browser'&&data.version===1)replacement=data.state;
  else if(data?.version===1&&data.tables){
   // Import an existing local-server backup without exposing it to GitHub.
   const tables=data.tables;replacement=emptyState();const ids=new Map();
   for(const job of tables.opportunities||[]){const match=research.opportunities.find(j=>j.url&&j.url===job.url&&j.cycle===job.cycle);const id=match?match.id:replacement.nextId--;ids.set(job.id,id);if(!match)replacement.manual.push({...job,id});}
   for(const track of tables.tracking||[])replacement.tracking[ids.get(track.opportunity_id)]={...track,opportunity_id:ids.get(track.opportunity_id)};
   replacement.contacts=tables.contacts||[];replacement.interactions=tables.interactions||[];
   replacement.contact_opportunities=(tables.contact_opportunities||[]).filter(l=>ids.has(l.opportunity_id)).map(l=>({...l,opportunity_id:ids.get(l.opportunity_id)}));
   replacement.settings=Object.fromEntries((tables.settings||[]).filter(r=>r.key==='permit_status').map(r=>[r.key,r.value]));
  }else throw Error('Unsupported backup');
  if(!replacement||!Array.isArray(replacement.manual)||!Array.isArray(replacement.contacts)||!Array.isArray(replacement.interactions)||!Array.isArray(replacement.contact_opportunities)||!Number.isInteger(replacement.nextId)||replacement.nextId>=0||!replacement.tracking||!replacement.edits||!replacement.settings)throw Error('Invalid backup; existing data retained');
  const recovery=JSON.stringify({format:'northbound-browser',version:1,state:s});localStorage.setItem('northbound-before-restore',recovery);
  for(const k of Object.keys(emptyState()))s[k]=replacement[k];return {ok:true};
 });
 return stateOperation(true,s=>{
  const parts=path.split('/'),id=Number(parts[1]);
  if(path==='settings'){Object.assign(s.settings,data);return {ok:true};}
  if(parts[0]==='tracking'){s.tracking[id]={...s.tracking[id],...data};return {ok:true};}
  if(parts[0]==='opportunities'){
   if(method==='POST'){if(!data.employer?.trim()||!data.role?.trim())throw Error('Employer and role are required');const id=s.nextId--;s.manual.push({id,city:'',category:'Economic consulting',recruiting:'Monitor',authorization:'Employer support unknown',origin:'manual',updated:new Date().toISOString(),first_discovered:new Date().toISOString(),...data});s.tracking[id]={...trackingDefaults,saved:1};return {id};}
   s.edits[id]={...s.edits[id],...data,updated:new Date().toISOString()};return {ok:true};
  }
  if(parts[0]==='contacts'){
   if(parts.length===1){if(!data.name?.trim())throw Error('Contact name required');const id=s.nextId--;s.contacts.push({id,tags:'',...data});return {id};}
   const c=s.contacts.find(c=>c.id===id);if(!c)throw Error('Contact not found');
   if(parts[2]==='interactions'){if(!data.date)throw Error('Date required');const iid=s.nextId--;s.interactions.push({id:iid,contact_id:id,...data});Object.assign(c,{followup:data.followup,channel:data.channel,response:data.response});return {id:iid};}
   if(parts[2]==='links'){const oid=Number(data.opportunity_id);if(!s.contact_opportunities.some(l=>l.contact_id===id&&l.opportunity_id===oid))s.contact_opportunities.push({contact_id:id,opportunity_id:oid});return {ok:true};}
   Object.assign(c,data);return {ok:true};
  }
  throw Error('Unsupported operation');
 });
};
document.addEventListener('click',async event=>{const a=event.target.closest('a');if(!a)return;const href=a.getAttribute('href');if(href!=='/api/backup'&&!href?.startsWith('/api/export/'))return;event.preventDefault();try{
 if(href==='/api/backup'){const state=await stateOperation(false,s=>s);await saveDownload('northbound-browser-backup.json',JSON.stringify({format:'northbound-browser',version:1,state}), 'application/json');}
 else{const table=href.split('/').at(-1).replace('.csv',''),d=await window.pagesAPI('data'),rows=d[table]||[];const keys=[...new Set(rows.flatMap(r=>Object.keys(r)))];const cell=v=>{let s=String(v??'');if(/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};await saveDownload(table+'.csv',[keys,...rows.map(r=>keys.map(k=>r[k]))].map(r=>r.map(cell).join(',')).join('\r\n'),'text/csv');}
 }catch(e){alert(e.message);}
});

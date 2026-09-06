"""AI-powered test generation, authenticated crawling, planning and realistic data."""
from __future__ import annotations
import json, os
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse
from .agentic import AgenticAI
_DOM_EXTRACT_JS="""(function(){return {title:document.title,body_text:(document.body.innerText||'').trim().slice(0,12000),headings:Array.from(document.querySelectorAll('h1,h2,h3')).slice(0,6).map(h=>h.innerText.trim()).filter(Boolean),forms:Array.from(document.querySelectorAll('form')).map(f=>({id:f.id||'',action:f.action||'',method:f.method||'get'})),inputs:Array.from(document.querySelectorAll('input,textarea,select')).slice(0,20).map(el=>({tag:el.tagName.toLowerCase(),id:el.id||'',name:el.getAttribute('name')||'',type:el.getAttribute('type')||'',placeholder:el.getAttribute('placeholder')||'',label:(document.querySelector('label[for="'+el.id+'"]')||{}).innerText||''})),buttons:Array.from(document.querySelectorAll('button,input[type=submit],input[type=button]')).slice(0,10).map(b=>({tag:b.tagName.toLowerCase(),id:b.id||'',text:(b.innerText||b.value||'').trim(),type:b.getAttribute('type')||''})),links:Array.from(document.querySelectorAll('a[href]')).slice(0,30).map(a=>({id:a.id||'',text:a.innerText.trim(),href:a.getAttribute('href')||'',download:a.hasAttribute('download')})),tables:Array.from(document.querySelectorAll('table')).slice(0,3).map(t=>({id:t.id||'',headers:Array.from(t.querySelectorAll('th')).map(th=>th.innerText.trim())}))};})()"""
_SYSTEM_PROMPT="""You are an expert QA engineer generating runnable browser tests from OBSERVED page data. Never invent behavior. Use only selectors, text, titles, headings, hrefs, attributes and element types present in page_info. Never invent credentials, success messages, result text, URLs or API responses. Never fill password inputs with fabricated credentials. File inputs require a real existing file path. Download only observed downloadable links. Prefer element_present when behavior is not directly observable. Return ONLY JSON with test_suite and tests."""
class TestGenerator:
 def __init__(self,provider='none',model='gpt-4o-mini'):
  self.provider=provider.lower();self.model=model;self.client=None
  if self.provider=='openai' and os.getenv('OPENAI_API_KEY'):
   from openai import OpenAI;self.client=OpenAI(api_key=os.environ['OPENAI_API_KEY'])
  self.agent=AgenticAI(provider,model)
 def generate(self,url,output_path,browser='chromium',base_url='',max_pages=1):
  pages=self._discover_pages(url,browser,base_url,max_pages=max_pages) if int(max_pages)>1 else [(self._extract_page_info(url,browser,base_url),self._relative(url,base_url))];return self._write_generated(pages,output_path)
 def generate_authenticated(self,url,output_path,login,browser='chromium',base_url='',max_pages=5):return self._write_generated(self._discover_authenticated_pages(url,browser,base_url,login,max_pages),output_path)
 def _write_generated(self,pages,output_path):
  all_tests=[];suite_title='Generated Suite'
  for page_info,relative_url in pages:
   suite_title=suite_title if suite_title!='Generated Suite' else(page_info.get('title') or suite_title);suite=self._ai_generate(page_info,relative_url) if self.client else self._heuristic_generate(page_info,relative_url)
   if self.client:suite=self._sanitize_suite(suite,page_info,relative_url)
   for test in suite.get('tests',[]):test['id']=f'GEN-{len(all_tests)+1:03d}';test['url']=relative_url;all_tests.append(test)
  if not all_tests:raise RuntimeError('No testable pages were discovered')
  out=Path(output_path);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'test_suite':f'{suite_title} — Generated Tests','tests':all_tests},indent=2,ensure_ascii=False),encoding='utf-8');return str(out.resolve())
 def _discover_pages(self,url,browser,base_url,max_pages=1,login=None):
  from playwright.sync_api import sync_playwright
  max_pages=max(1,min(int(max_pages),50));target=f"{base_url.rstrip('/')}/{url.lstrip('/')}" if base_url and url.startswith('/') else url;origin=urlparse(target).netloc;queue=[target];seen=set();discovered=[]
  with sync_playwright() as p:
   b=getattr(p,browser).launch(headless=True);context=b.new_context();page=context.new_page()
   try:
    if login:
     self._perform_login(page,login);success=login.get('success_url');queue=[str(success)] if success else [target]
    while queue and len(discovered)<max_pages:
     current=urldefrag(queue.pop(0))[0]
     if current in seen:continue
     seen.add(current)
     try:page.goto(current,wait_until='domcontentloaded',timeout=15000);info=page.evaluate(_DOM_EXTRACT_JS)
     except Exception:continue
     info['url']=current;info['target_url']=current;discovered.append((info,self._relative(current,base_url)))
     for link in info.get('links',[]):
      href=str(link.get('href',''))
      if not href or link.get('download'):continue
      child=urldefrag(urljoin(current,href))[0];parsed=urlparse(child)
      if parsed.scheme in {'http','https'} and parsed.netloc==origin and child not in seen and child not in queue:queue.append(child)
   finally:b.close()
  return discovered
 def _discover_authenticated_pages(self,url,browser,base_url,login,max_pages):return self._discover_pages(url,browser,base_url,max_pages=max_pages,login=login)
 @staticmethod
 def _perform_login(page,login):
  if not isinstance(login,dict):raise ValueError('login must be an object')
  page.goto(str(login.get('url') or login.get('login_url') or ''),wait_until='domcontentloaded',timeout=15000)
  for key in ('username_selector','password_selector','submit_selector'):
   if not login.get(key):raise ValueError(f'Authenticated crawler login requires {key}')
  page.locator(login['username_selector']).fill(str(login.get('username','')));page.locator(login['password_selector']).fill(str(login.get('password','')));page.locator(login['submit_selector']).click()
  if login.get('success_url'):page.wait_for_url(str(login['success_url']),wait_until='domcontentloaded',timeout=15000)
 def _extract_page_info(self,url,browser,base_url):
  pages=self._discover_pages(url,browser,base_url,max_pages=1);return pages[0][0] if pages else {}
 def _ai_generate(self,page_info,relative_url):
  prompt=json.dumps({'url':relative_url,'page_info':page_info},ensure_ascii=False);resp=self.client.chat.completions.create(model=self.model,temperature=.1,messages=[{'role':'system','content':_SYSTEM_PROMPT},{'role':'user','content':prompt}]);raw=(resp.choices[0].message.content or '{}').strip()
  if raw.startswith('```'):raw=raw.split('\n',1)[-1].rsplit('```',1)[0]
  suite=json.loads(raw);suite.setdefault('test_suite',page_info.get('title') or 'Generated Suite');suite['tests']=suite.get('tests',[]) if isinstance(suite.get('tests',[]),list) else [];return suite
 def _sanitize_suite(self,suite,page_info,relative_url):
  inputs,buttons,links=page_info.get('inputs',[]),page_info.get('buttons',[]),page_info.get('links',[]);file_selectors={self._selector(x) for x in inputs if x.get('type')=='file'};download_selectors={self._selector(x) for x in links if self._selector(x) and(x.get('download') or self._looks_downloadable(x.get('href','')))};cleaned=[]
  for index,test in enumerate(suite.get('tests',[]),1):
   if not isinstance(test,dict):continue
   test['id']=test.get('id') or f'GEN-{index:03d}';test['url']=test.get('url') or relative_url;steps=[]
   for step in test.get('steps',[]) or []:
    if not isinstance(step,dict):continue
    action=str(step.get('action','')).lower().strip();selector=step.get('selector')
    if action in {'fill','type'} and selector in file_selectors:continue
    if action in {'upload','set_input_files'} and(selector not in file_selectors or not Path(str(step.get('value',''))).expanduser().is_file()):continue
    if action=='download' and selector not in download_selectors:continue
    steps.append(step)
   test['steps']=steps;test['validations']=list(test.get('validations',[]) or []);test['error_checks']=['console_errors'] if 'console_errors' in(test.get('error_checks') or []) else[];cleaned.append(test)
  return {'test_suite':suite.get('test_suite') or 'Generated Suite','tests':cleaned or self._heuristic_generate(page_info,relative_url)['tests']}
 @staticmethod
 def _looks_downloadable(href):return any(str(href).lower().split('?',1)[0].endswith(ext) for ext in('.csv','.pdf','.json','.xlsx','.zip','.txt'))
 def _heuristic_generate(self,page_info,relative_url):
  title=page_info.get('title') or 'Generated Suite';validations=[{'type':'element_present','selector':self._selector(e)} for e in page_info.get('inputs',[])[:4]+page_info.get('buttons',[])[:2] if self._selector(e)];validations +=[{'type':'text_contains','selector':'body','expected':h} for h in page_info.get('headings',[])[:1]];tests=[{'id':'GEN-001','name':'Page loads with expected elements','url':relative_url,'steps':[],'validations':validations,'error_checks':['console_errors']}];all_inputs=page_info.get('inputs',[]);text_inputs=[i for i in all_inputs if i.get('type','text') in('','text','search')];buttons=page_info.get('buttons',[]);has_password=any(str(i.get('type','')).lower()=='password' for i in all_inputs)
  if text_inputs and buttons and not has_password:
   steps=[{'action':'type','selector':self._selector(i),'value':'test'} for i in text_inputs[:2] if self._selector(i)]
   if self._selector(buttons[0]):steps.append({'action':'click','selector':self._selector(buttons[0])})
   tests.append({'id':'GEN-002','name':'Form submission','url':relative_url,'steps':steps,'validations':[],'error_checks':['console_errors']})
  for tbl in page_info.get('tables',[])[:1]:
   if tbl.get('headers'):
    sel=f"#{tbl['id']}" if tbl.get('id') else 'table';tests.append({'id':f'GEN-{len(tests)+1:03d}','name':'Table structure validation','url':relative_url,'steps':[{'action':'wait','selector':sel,'timeout':5000}],'validations':[{'type':'table_validation','selector':sel,'expected_columns':tbl['headers'],'row_condition':''}],'error_checks':[]})
  return {'test_suite':f'{title} — Generated Tests','tests':tests}
 @staticmethod
 def _selector(element):
  if element.get('id'):return f"#{element['id']}"
  if element.get('name'):return f"[name=\"{element['name']}\"]"
  if element.get('type'):return f"{element.get('tag','input')}[type=\"{element['type']}\"]"
  return ''
 @staticmethod
 def _relative(url,base_url):
  if not base_url or not url.startswith(base_url):
   parsed=urlparse(url);return parsed.path+(("?"+parsed.query) if parsed.query else '') or '/'
  rel=url[len(base_url):];return rel or '/'

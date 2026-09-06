from __future__ import annotations
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from .element_locator import AIElementLocator
from .self_healing import SelfHealing

class PlaywrightEngine:
    """Thin synchronous Playwright adapter used by the test runner."""
    def __init__(self,browser_name="chromium",headless=True,timeout=30000,ai_provider="none",ai_model="gpt-4o-mini",self_healing=True,healing_confidence=0.70,artifact_dir="reports"):
        self.browser_name=browser_name; self.headless=headless; self.timeout=timeout; self.artifact_dir=Path(artifact_dir); self.ai_locator=AIElementLocator(ai_provider,ai_model); self.self_healing=SelfHealing(ai_provider,ai_model,healing_confidence) if self_healing else None; self.playwright=None; self.browser=None; self.context=None; self.page=None; self.console_errors=[]; self.api_errors=[]; self.downloads=[]; self.uploads=[]; self.healed_selectors=[]; self.dialogs=[]
    def start(self):
        self.playwright=sync_playwright().start(); self.browser=getattr(self.playwright,self.browser_name).launch(headless=self.headless); self.context=self.browser.new_context(accept_downloads=True); self.page=self.context.new_page(); self.page.set_default_timeout(self.timeout); self._attach_listeners()
    def stop(self):
        if self.context:self.context.close()
        if self.browser:self.browser.close()
        if self.playwright:self.playwright.stop()
        self.page=self.context=self.browser=self.playwright=None
    def _attach_listeners(self):
        assert self.page is not None; self.page.on("console",lambda msg:self.console_errors.append(msg.text) if msg.type=="error" else None); self.page.on("requestfailed",lambda request:self.api_errors.append(f"{request.method} {request.url}: {request.failure}")); self.page.on("dialog",self._handle_dialog)
    def _handle_dialog(self,dialog):
        action=getattr(self,"_dialog_action","dismiss"); self.dialogs.append({"type":dialog.type,"message":dialog.message,"action":action}); dialog.accept() if action=="accept" else dialog.dismiss()
    def open(self,url,base_url=""):
        assert self.page is not None; target=f"{base_url.rstrip('/')}/{url.lstrip('/')}" if base_url and url.startswith("/") else url; self.page.goto(target,wait_until="domcontentloaded")
    def _resolve_locator(self,selector=None,description=""):
        assert self.page is not None
        if selector:return self.page.locator(selector)
        if description:return self.ai_locator.find_element(self.page,description)
        raise ValueError("Step requires either 'selector' or 'description'.")
    def _try_heal(self,selector,description,action_fn,timeout):
        locator=self.page.locator(selector)
        try:return action_fn(locator)
        except Exception as original:
            if not self.self_healing:raise
            healed_selector=self.self_healing.heal_selector(self.page,selector,description)
            if healed_selector:
                self.healed_selectors.append({"failed_selector":selector,"healed_selector":healed_selector,"reason":self.self_healing.last_reason,"confidence":self.self_healing.last_confidence}); return action_fn(self.page.locator(healed_selector))
            raise original
    def _set_cookie(self,cookie):
        assert self.context is not None and self.page is not None
        item=dict(cookie)
        if "url" not in item and "domain" not in item:
            parsed=urlparse(self.page.url); item["url"]=f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else self.page.url
        try:
            self.context.add_cookies([item])
        except Exception:
            # Non-HttpOnly cookies can be bootstrapped directly in the current origin.
            if item.get("httpOnly"):
                raise
            name=str(item.get("name","")).replace("\\","\\\\").replace("'","\\'"); value=str(item.get("value","")).replace("\\","\\\\").replace("'","\\'"); path=str(item.get("path","/"))
            self.page.evaluate("(x)=>document.cookie=x",f"{name}={value}; Path={path}")
    def _set_local_storage(self,values):
        assert self.page is not None; self.page.evaluate("""(items)=>{for(const [k,v] of Object.entries(items))localStorage.setItem(k,String(v));}""",values)
    def _login(self,value):
        if not isinstance(value,dict):raise ValueError("Login step value must be an object")
        us,ps,ss=value.get("username_selector"),value.get("password_selector"),value.get("submit_selector")
        if not us or not ps or not ss:raise ValueError("Login requires username_selector, password_selector and submit_selector")
        self.page.locator(us).fill(str(value.get("username",""))); self.page.locator(ps).fill(str(value.get("password",""))); self.page.locator(ss).click()
        if value.get("success_url"): self.page.wait_for_url(str(value["success_url"]),wait_until=value.get("wait_until","domcontentloaded"),timeout=self.timeout)
        elif value.get("wait_for_load_state"): self.page.wait_for_load_state(str(value["wait_for_load_state"]))
    def _switch_tab(self,value):
        assert self.context is not None; pages=self.context.pages
        if not pages:raise ValueError("No browser pages are open")
        if value is None or value=="last":target=pages[-1]
        elif isinstance(value,int) or str(value).isdigit():
            index=int(value)
            if index<0 or index>=len(pages):raise IndexError(f"Tab index out of range: {index}")
            target=pages[index]
        else:
            target=next((p for p in pages if str(value) in p.url),None)
            if target is None:raise ValueError(f"No tab URL matched {value!r}")
        target.bring_to_front(); self.page=target; self.page.set_default_timeout(self.timeout); return target
    def run_step(self,step):
        assert self.page is not None; action=step.action.lower().strip(); selector=step.selector; description=getattr(step,"description","") or ""; value=step.value; value_text="" if value is None else str(value); timeout=getattr(step,"timeout",self.timeout)
        if action in {"evaluate","javascript","js"}:
            if not value_text.strip():raise ValueError("Evaluate step requires JavaScript in 'value'.")
            return self.page.evaluate(value_text)
        if action in {"set_cookie","cookie"}:
            cookies=value if isinstance(value,list) else [value]
            if not all(isinstance(c,dict) for c in cookies):raise ValueError("set_cookie value must be a cookie object or list of cookie objects")
            for cookie in cookies:self._set_cookie(cookie)
            return
        if action in {"set_local_storage","local_storage"}:
            if not isinstance(value,dict):raise ValueError("set_local_storage value must be an object")
            self._set_local_storage(value); return
        if action in {"login","login_form"}:return self._login(value)
        if action in {"accept_dialog","accept_alert"}:self._dialog_action="accept"; return
        if action in {"dismiss_dialog","dismiss_alert"}:self._dialog_action="dismiss"; return
        if action in {"open_popup","click_popup"}:
            locator=self._resolve_locator(selector,description)
            with self.page.expect_popup(timeout=timeout) as popup_info:locator.click(timeout=timeout)
            popup=popup_info.value; popup.wait_for_load_state("domcontentloaded",timeout=timeout); self.page=popup; self.page.set_default_timeout(self.timeout); self._attach_listeners(); return popup
        if action in {"switch_tab","switch_page"}:return self._switch_tab(value)
        if action in {"close_tab","close_page"}:
            if len(self.context.pages)<=1:raise ValueError("Cannot close the only browser tab")
            self.page.close(); return self._switch_tab("last")
        if action in {"press","keyboard"} and not selector and not description:self.page.keyboard.press(value_text); return
        if action=="wait_for_load_state":self.page.wait_for_load_state(value_text or "networkidle",timeout=timeout); return
        if action in {"upload","set_input_files"}:
            upload_path=Path(value_text).expanduser()
            if not upload_path.exists() or not upload_path.is_file():raise FileNotFoundError(f"Upload file does not exist: {upload_path}")
            self.uploads.append(str(upload_path.resolve()))
        locator=self._resolve_locator(selector,description); heal=lambda fn:self._try_heal(selector,description,fn,timeout) if selector and self.self_healing else fn(locator)
        if action in {"type","fill"}:heal(lambda l:l.fill(value_text,timeout=timeout))
        elif action=="click":heal(lambda l:l.click(timeout=timeout))
        elif action in {"check","checkbox"}:heal(lambda l:l.check(timeout=timeout))
        elif action=="uncheck":heal(lambda l:l.uncheck(timeout=timeout))
        elif action in {"select","select_option"}:heal(lambda l:l.select_option(value_text,timeout=timeout))
        elif action=="hover":heal(lambda l:l.hover(timeout=timeout))
        elif action in {"press","keyboard"}:heal(lambda l:l.press(value_text,timeout=timeout))
        elif action in {"upload","set_input_files"}:heal(lambda l:l.set_input_files(value_text,timeout=timeout))
        elif action in {"wait","wait_for_selector"}:heal(lambda l:l.wait_for(state="visible",timeout=timeout))
        elif action in {"wait_for_response","response"}:
            with self.page.expect_response(value_text,timeout=timeout) as response_info:
                if selector or description:locator.click(timeout=timeout)
            return response_info.value
        elif action=="download":
            with self.page.expect_download(timeout=timeout) as download_info:
                if selector or description:locator.click(timeout=timeout)
            download=download_info.value; target=self.artifact_dir/"downloads"/download.suggested_filename; target.parent.mkdir(parents=True,exist_ok=True); download.save_as(str(target)); self.downloads.append(str(target)); return str(target)
        else:raise ValueError(f"Unsupported Playwright action: {step.action!r}")
    def response_text(self):assert self.page is not None; return self.page.locator("body").inner_text()
    def screenshot(self,path):
        assert self.page is not None; target=Path(path); target.parent.mkdir(parents=True,exist_ok=True); self.page.screenshot(path=str(target),full_page=True); return str(target)
    def errors(self):return self.console_errors,self.api_errors

from __future__ import annotations

import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser(); parser.add_argument('--browser',default='chromium'); parser.add_argument('--url',default='http://127.0.0.1:8000/'); parser.add_argument('--output',default='tests/baselines/demo_home.png'); args=parser.parse_args()
with sync_playwright() as p:
    browser=getattr(p,args.browser).launch(headless=True); page=browser.new_page(viewport={"width":1280,"height":720}); page.goto(args.url,wait_until='domcontentloaded'); Path(args.output).parent.mkdir(parents=True,exist_ok=True); page.screenshot(path=args.output,full_page=True); browser.close()
print(args.output)

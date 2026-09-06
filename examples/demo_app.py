import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

SEARCH_HTML = '''<!doctype html>
<html><body>
<h1>AI Testing Demo</h1>
<form id="search-form">
  <input id="query" placeholder="Search">
  <button id="submit" type="submit">Search</button>
</form>
<div id="result" class="result-container"></div>
<p><a id="download" href="/download/sample.csv" download="sample.csv">Download sample CSV</a></p>
<form id="upload-form" enctype="multipart/form-data" method="post" action="/upload">
  <input id="file" name="file" type="file">
  <button id="upload" type="submit">Upload</button>
</form>
<p><a href="/table">Customer table</a> <a href="/auth">Login demo</a> <a href="/page2">Page two</a></p>
<script>
document.getElementById('search-form').addEventListener('submit', async function(event) {
  event.preventDefault();
  const q = document.getElementById('query').value;
  const result = document.getElementById('result');
  try {
    const response = await fetch('/api/search?q=' + encodeURIComponent(q));
    if (!response.ok) throw new Error('HTTP ' + response.status);
    const data = await response.json();
    result.textContent = 'Search result: ' + data.results[0] + ' Query: ' + q;
    result.classList.add('visible');
  } catch (error) { result.textContent = 'Search failed: ' + error.message; result.classList.add('visible'); }
});
</script>
</body></html>'''

TABLE_HTML = '''<!doctype html><html><body><h1>Customer Table</h1>
<table id="customers"><thead><tr><th>First Name</th><th>Last Name</th><th>Country</th></tr></thead>
<tbody><tr><td>Asha</td><td>Patil</td><td>India</td></tr><tr><td>Rahul</td><td>Shah</td><td>India</td></tr></tbody></table>
<p><a href="/">Home</a></p></body></html>'''

API_HTML = '''<!doctype html><html><body><h1>API Test Demo</h1>
<form id="echo-form"><input id="message" value="hello"><button id="send" type="submit">Send</button></form><div id="echo-result"></div>
<script>document.getElementById('echo-form').addEventListener('submit', async e => { e.preventDefault(); const message=document.getElementById('message').value;
const r=await fetch('/api/echo',{method:'POST',headers:{'X-Test-Header':'framework'},body:JSON.stringify({message})}); const d=await r.json(); document.getElementById('echo-result').textContent=d.message; });</script></body></html>'''

AUTH_HTML = '''<!doctype html><html><body><h1>Login Demo</h1>
<form id="login-form"><input id="username" name="username"><input id="password" name="password" type="password"><button id="login" type="submit">Login</button></form><div id="auth-result"></div>
<script>document.getElementById('login-form').addEventListener('submit', async e => { e.preventDefault(); const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username.value,password:password.value})}); const d=await r.json(); if(d.success){document.cookie='session=demo-session; Path=/'; localStorage.setItem('role','user'); location.href='/protected';} else auth-result.textContent='Login failed'; });</script></body></html>'''

PROTECTED_HTML = '''<!doctype html><html><body><h1>Protected Area</h1><p id="session-status">Authenticated session</p><a href="/">Home</a></body></html>'''

PAGE2_HTML = '''<!doctype html><html><body><h1>Page Two</h1><p>Second discovered page</p><a href="/table">Customer table</a><a href="/">Home</a></body></html>'''

POPUP_HTML = '''<!doctype html><html><body><h1>Popup Page</h1><p>Popup opened successfully</p></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, content_type, payload, headers=None):
        self.send_response(code); self.send_header('Content-Type', content_type); self.send_header('Content-Length', str(len(payload)))
        for key, value in (headers or {}).items(): self.send_header(key, value)
        self.end_headers(); self.wfile.write(payload)

    def do_GET(self):
        path, _, query = self.path.partition('?')
        if path == '/api/search':
            params = parse_qs(query); payload = json.dumps({'success': True, 'results': ['OpenAI is an AI research and deployment company.'], 'query': params.get('q', [''])[0]}).encode(); self._send(200, 'application/json', payload, {'X-Demo-API': 'search'}); return
        if path == '/download/sample.csv':
            payload = b'First Name,Last Name,Country\nAsha,Patil,India\nRahul,Shah,India\n'; self._send(200, 'text/csv', payload, {'Content-Disposition': 'attachment; filename="sample.csv"'}); return
        if path == '/api/login':
            self._send(405, 'application/json', b'{"success":false}'); return
        if path == '/protected':
            cookie = self.headers.get('Cookie', '')
            if 'session=demo-session' not in cookie: self._send(401, 'text/plain', b'Unauthorized'); return
            self._send(200, 'text/html; charset=utf-8', PROTECTED_HTML.encode()); return
        if path == '/auth': html = AUTH_HTML
        elif path == '/api-demo': html = API_HTML
        elif path == '/table': html = TABLE_HTML
        elif path == '/page2': html = PAGE2_HTML
        elif path == '/popup': html = POPUP_HTML
        else: html = SEARCH_HTML
        self._send(200, 'text/html; charset=utf-8', html.encode())

    def do_POST(self):
        path, _, _ = self.path.partition('?'); length = int(self.headers.get('Content-Length', '0')); raw = self.rfile.read(length)
        if path == '/api/login':
            try: data = json.loads(raw or b'{}')
            except ValueError: data = {}
            if data.get('username') == 'demo' and data.get('password') == 'secret':
                self._send(200, 'application/json', b'{"success":true}', {'Set-Cookie': 'session=demo-session; Path=/'}); return
            self._send(401, 'application/json', b'{"success":false}'); return
        if path == '/api/echo':
            try: data = json.loads(raw or b'{}')
            except ValueError: data = {}
            payload = json.dumps({'success': True, 'message': data.get('message', ''), 'received': data}).encode(); self._send(200, 'application/json', payload, {'X-Demo-Response': 'echo'}); return
        if path == '/upload':
            payload = json.dumps({'success': True, 'bytes_received': len(raw)}).encode(); self._send(200, 'application/json', payload); return
        self._send(404, 'text/plain', b'Not found')

    def log_message(self, *_): pass


if __name__ == '__main__':
    print('Demo app: http://127.0.0.1:8000')
    HTTPServer(('127.0.0.1', 8000), Handler).serve_forever()

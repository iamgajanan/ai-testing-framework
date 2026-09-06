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
  } catch (error) {
    result.textContent = 'Search failed: ' + error.message;
    result.classList.add('visible');
  }
});
</script>
</body></html>'''

TABLE_HTML = '''<!doctype html>
<html><body><h1>Customer Table</h1>
<table id="customers"><thead><tr><th>First Name</th><th>Last Name</th><th>Country</th></tr></thead>
<tbody><tr><td>Asha</td><td>Patil</td><td>India</td></tr><tr><td>Rahul</td><td>Shah</td><td>India</td></tr></tbody></table>
</body></html>'''

API_HTML = '''<!doctype html><html><body><h1>API Test Demo</h1>
<form id="echo-form"><input id="message" value="hello"><button id="send" type="submit">Send</button></form>
<div id="echo-result"></div>
<script>document.getElementById('echo-form').addEventListener('submit', async e => {
 e.preventDefault(); const message=document.getElementById('message').value;
 const r=await fetch('/api/echo',{method:'POST',headers:{'X-Test-Header':'framework'},body:JSON.stringify({message})});
 const d=await r.json(); document.getElementById('echo-result').textContent=d.message;
});</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, content_type, payload, headers=None):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        for key, value in (headers or {}).items(): self.send_header(key, value)
        self.end_headers(); self.wfile.write(payload)

    def do_GET(self):
        path, _, query = self.path.partition('?')
        if path == '/api/search':
            params = parse_qs(query)
            payload = json.dumps({'success': True, 'results': ['OpenAI is an AI research and deployment company.'], 'query': params.get('q', [''])[0]}).encode()
            self._send(200, 'application/json', payload, {'X-Demo-API': 'search'})
            return
        if path == '/download/sample.csv':
            payload = b'First Name,Last Name,Country\nAsha,Patil,India\nRahul,Shah,India\n'
            self._send(200, 'text/csv', payload, {'Content-Disposition': 'attachment; filename="sample.csv"'})
            return
        if path == '/api-demo': html = API_HTML
        elif path == '/table': html = TABLE_HTML
        else: html = SEARCH_HTML
        self._send(200, 'text/html; charset=utf-8', html.encode())

    def do_POST(self):
        path, _, _ = self.path.partition('?')
        if path == '/api/echo':
            length = int(self.headers.get('Content-Length', '0'))
            raw = self.rfile.read(length)
            try: data = json.loads(raw or b'{}')
            except ValueError: data = {}
            payload = json.dumps({'success': True, 'message': data.get('message', ''), 'received': data}).encode()
            self._send(200, 'application/json', payload, {'X-Demo-Response': 'echo'})
            return
        if path == '/upload':
            # Demo endpoint intentionally accepts any upload and returns metadata.
            length = int(self.headers.get('Content-Length', '0'))
            body = self.rfile.read(length)
            payload = json.dumps({'success': True, 'bytes_received': len(body)}).encode()
            self._send(200, 'application/json', payload)
            return
        self._send(404, 'text/plain', b'Not found')

    def log_message(self, *_): pass


if __name__ == '__main__':
    print('Demo app: http://127.0.0.1:8000')
    HTTPServer(('127.0.0.1', 8000), Handler).serve_forever()

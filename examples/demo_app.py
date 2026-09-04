import json
from http.server import BaseHTTPRequestHandler, HTTPServer

SEARCH_HTML = '''<!doctype html>
<html><body>
<h1>AI Testing Demo</h1>
<form onsubmit="return search()">
  <input id="query" placeholder="Search">
  <button id="submit">Search</button>
</form>
<div id="result" class="result-container"></div>
<script>
async function search(){
  const q=document.getElementById('query').value;
  const response = await fetch('/api/search?q=' + encodeURIComponent(q));
  const data = await response.json();
  document.getElementById('result').textContent='Search result: '+data.results[0]+' Query: '+q;
  return false;
}
</script>
</body></html>'''

TABLE_HTML = '''<!doctype html>
<html><body>
<h1>Customer Table</h1>
<table id="customers">
  <thead><tr><th>First Name</th><th>Last Name</th><th>Country</th></tr></thead>
  <tbody>
    <tr><td>Asha</td><td>Patil</td><td>India</td></tr>
    <tr><td>Rahul</td><td>Shah</td><td>India</td></tr>
  </tbody>
</table>
</body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path, _, query = self.path.partition('?')
        if path == '/api/search':
            params = dict(item.split('=', 1) for item in query.split('&') if '=' in item)
            result = {'success': True, 'results': ['OpenAI is an AI research and deployment company.'], 'query': params.get('q', '')}
            payload = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        html = TABLE_HTML if path == '/table' else SEARCH_HTML
        payload = html.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    print('Demo app: http://127.0.0.1:8000')
    HTTPServer(('127.0.0.1', 8000), Handler).serve_forever()

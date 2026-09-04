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
function search(){
  const q=document.getElementById('query').value;
  document.getElementById('result').textContent='Search result: OpenAI is an AI research and deployment company. Query: '+q;
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
        html = TABLE_HTML if self.path.split('?', 1)[0] == '/table' else SEARCH_HTML
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    print('Demo app: http://127.0.0.1:8000')
    HTTPServer(('127.0.0.1', 8000), Handler).serve_forever()

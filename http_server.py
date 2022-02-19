from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

class HandleRequests(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        f = open('/var/lib/homebridge/'+self.path, 'r')
        val = f.readline()
        f.close()
        self.wfile.write(str(val))
        
    def do_PUT(self):
        self._set_headers()
        content_len = int(self.headers.getheader('content-length', 0))
        f = open('/var/lib/homebridge/'+self.path, 'w')
        f.write(self.rfile.read(content_len))
        f.close()

host = '127.0.0.1'
port = 8001
HTTPServer((host, port), HandleRequests).serve_forever()
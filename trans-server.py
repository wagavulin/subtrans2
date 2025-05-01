#!/usr/bin/env python

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from transformers import pipeline

g_model = pipeline("translation", model="staka/fugumt-en-ja")

class SubTransRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Hello, world!')

    def do_POST(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        print(params)
        content_len  = int(self.headers.get("content-length"))
        req_body = self.rfile.read(content_len).decode("utf-8")
        ans = g_model(req_body)
        translated = ans[0]["translation_text"]

        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()

        self.wfile.write(translated.encode())

if not len(sys.argv) == 2:
    print(f"usage: subtrans-server <port>")
    exit(1)
port = int(sys.argv[1])

server = HTTPServer(('', port), SubTransRequestHandler)
server.serve_forever()
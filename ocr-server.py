#!/usr/bin/env python

from PIL import Image
from io import BytesIO
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import pyocr

g_tool = pyocr.get_available_tools()[0]

class OcrRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Hello, World!")

    def do_POST(self):
        #parsed = urlparse(self.path)
        #params = parse_qs(parsed.query)
        #print(params)
        clen = int(self.headers.get("content-length"))
        print(f"clen: {clen}")
        req_body = self.rfile.read(clen)
        bio = BytesIO(req_body)
        img = Image.open(bio)
        txt:str = g_tool.image_to_string(img, lang="eng")
        
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        
        self.wfile.write(txt.encode())
                         

server = HTTPServer(("", 8000), OcrRequestHandler)
server.serve_forever()

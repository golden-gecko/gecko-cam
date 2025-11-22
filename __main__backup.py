import io
import socketserver

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Condition

from logger import get_logger


logger = get_logger()

page = '''
    <html>
        <head>
            <title>GeckoCam</title>
        </head>
        <body>
            <center><img src="stream.mjpg" with="800" height="600"></center>
        </body>
    </html>
'''

streaming_output = None


class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self._handle_root()
        elif self.path == '/stream.mjpg':
            self._handle_stream()
        else:
            self._handle_not_found()

    def _handle_root(self):
        content = page.encode('utf-8')

        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Length', len(content))
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(content)

    def _handle_stream(self):
        self.send_response(HTTPStatus.OK)
        self.send_header('Age', 0)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
        self.send_header('Pragma', 'no-cache')
        self.end_headers()

        try:
            while True:
                streaming_output = get_streaming_output()

                with streaming_output.condition:
                    streaming_output.condition.wait()

                    from __main__ import process_frame

                    image = process_frame(streaming_output.frame)
                    frame = image_to_frame(image)

                self.wfile.write(b'--FRAME\r\n')

                self.send_header('Content-Length', len(frame))
                self.send_header('Content-Type', 'image/jpeg')

                self.end_headers()

                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
        except Exception as e:
            logger.exception('Failed: %s', e)

    def _handle_not_found(self):
        self.send_error(HTTPStatus.NOT_FOUND)
        self.end_headers()


class StreamingOutput:
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            self.buffer.truncate()

            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()

            self.buffer.seek(0)

        return self.buffer.write(buf)


class StreamingServer(socketserver.ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def get_streaming_output():
    global streaming_output

    if not streaming_output:
        streaming_output = StreamingOutput()

    return streaming_output


def image_to_frame(image):
    buf = io.BytesIO()
    image.save(buf, format='JPEG')

    return buf.getvalue()

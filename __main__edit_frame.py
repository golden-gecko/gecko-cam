import cv2
import datetime
import io
import logging
import numpy
import picamera
import socketserver

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from PIL import Image, ImageDraw, ImageFont
from threading import Condition


page = '''
<html>
    <head>
        <title>GeckoCam</title>
    </head>
    <body>
        <center><img src="stream.mjpg" with="1024" height="768"></center>
    </body>
</html>
'''


class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


class StreamingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            content = page.encode('utf-8')

            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Length', len(content))
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(HTTPStatus.OK)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.send_header('Pragma', 'no-cache')
            self.end_headers()

            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                        # now add timestamp to jpeg
                        # Convert to PIL Image
                        cv2.CV_LOAD_IMAGE_COLOR = 1  # set flag to 1 to give colour image
                        numpyframe = numpy.fromstring(frame, dtype=numpy.uint8)
                        pil_frame = cv2.imdecode(numpyframe, cv2.CV_LOAD_IMAGE_COLOR)
                        # pil_frame = cv2.imdecode(frame,-1)
                        cv2_im_rgb = cv2.cvtColor(pil_frame, cv2.COLOR_BGR2RGB)



                        # cv2_im_rgb = cv2.GaussianBlur(cv2_im_rgb, (21, 21), 0)



                        pil_im = Image.fromarray(cv2_im_rgb)

                        draw = ImageDraw.Draw(pil_im)

                        # Choose a font
                        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 25)
                        myText = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

                        # Draw the text
                        color = 'rgb(255,255,255)'
                        # draw.text((0, 0), myText,fill = color, font=font)

                        # get text size
                        text_size = font.getsize(myText)

                        # set button size + 10px margins
                        button_size = (text_size[0] + 20, text_size[1] + 15)

                        # create image with correct size and black background
                        button_img = Image.new('RGBA', button_size, 'black')

                        # button_img.putalpha(128)
                        # put text on button with 10px margins
                        button_draw = ImageDraw.Draw(button_img)
                        button_draw.text((10, 5), myText, fill=color, font=font)

                        # put button on source image in position (0, 0)

                        pil_im.paste(button_img, (0, 0))
                        bg_w, bg_h = pil_im.size
                        '''
                        # WeatherSTEM logo in lower left
                        size = 64
                        WSLimg = Image.open('WeatherSTEMLogoSkyBackground.png')
                        WSLimg.thumbnail((size, size), Image.ANTIALIAS)
                        pil_im.paste(WSLimg, (0, bg_h - size))

                        # SkyWeather log in lower right
                        SWLimg = Image.open('SkyWeatherLogoSymbol.png')
                        SWLimg.thumbnail((size, size), Image.ANTIALIAS)
                        pil_im.paste(SWLimg, (bg_w - size, bg_h - size))
                        '''

                        # Save the image
                        buf = io.BytesIO()
                        pil_im.save(buf, format='JPEG')
                        frame = buf.getvalue()

                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Length', len(frame))
                    self.send_header('Content-Type', 'image/jpeg')
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning('Removed streaming client %s: %s', self.client_address, e)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    with picamera.PiCamera(resolution='1024x768', framerate=24) as camera:
        output = StreamingOutput()
        camera.start_recording(output, format='mjpeg')
        camera.annotate_foreground = picamera.Color(y=0.2, u=0, v=0)
        camera.annotate_background = picamera.Color(y=0.8, u=0, v=0)

        try:
            address = ('0.0.0.0', 8000)
            server = StreamingServer(address, StreamingHandler)
            server.serve_forever()
        finally:
            camera.stop_recording()

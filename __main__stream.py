import argparse
import cv2
import datetime
import imutils
import io
import logging
import picamera
import socketserver
import time

from http import HTTPStatus, server
from imutils.video import VideoStream
from threading import Condition


logger = None
output = None

page = '''
<html>
    <head>
        <title>GeckoCam</title>
    </head>
    <body>
        <center><img src="stream.mjpg" ></center>
    </body>
</html>
'''


class StreamingOutput:
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


class StreamingHandler(server.BaseHTTPRequestHandler):
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

                    '''
                    logger.debug('Frame size: %d', output.buffer.getbuffer().nbytes)

                    from PIL import Image

                    im = Image.open(output.buffer)
                    im.save('/home/pi/camera/frame.jpg')
                    '''

                    import io
                    import picamera
                    import logging
                    from threading import Condition
                    from PIL import ImageFont, ImageDraw, Image
                    import cv2
                    import traceback
                    from io import StringIO
                    import numpy as np
                    import datetime as dt

                    frame = output.frame

                    '''
                    # Convert to PIL Image
                    cv2.CV_LOAD_IMAGE_COLOR = 1  # set flag to 1 to give colour image
                    npframe = np.fromstring(frame, dtype=np.uint8)
                    pil_frame = cv2.imdecode(npframe, cv2.CV_LOAD_IMAGE_COLOR)
                    # pil_frame = cv2.imdecode(frame,-1)
                    cv2_im_rgb = cv2.cvtColor(pil_frame, cv2.COLOR_BGR2RGB)
                    pil_im = Image.fromarray(cv2_im_rgb)

                    draw = ImageDraw.Draw(pil_im)

                    # Choose a font
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 25)
                    myText = "SkyWeather " + dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # Draw the text
                    color = 'rgb(255,255,255)'
                    # draw.text((0, 0), myText,fill = color, font=font)

                    # get text size
                    text_size = font.getsize(myText)

                    # set button size + 10px margins
                    button_size = (text_size[0] + 20, text_size[1] + 10)

                    # create image with correct size and black background
                    button_img = Image.new('RGBA', button_size, "black")

                    # button_img.putalpha(128)
                    # put text on button with 10px margins
                    button_draw = ImageDraw.Draw(button_img)
                    button_draw.text((10, 5), myText, fill=color, font=font)

                    # put button on source image in position (0, 0)
                    '''

                    '''
                    pil_im.paste(button_img, (0, 0))
                    bg_w, bg_h = pil_im.size
                    # WeatherSTEM logo in lower left
                    size = 64
                    WSLimg = Image.open("WeatherSTEMLogoSkyBackground.png")
                    WSLimg.thumbnail((size, size), Image.ANTIALIAS)
                    pil_im.paste(WSLimg, (0, bg_h - size))

                    # SkyWeather log in lower right
                    SWLimg = Image.open("SkyWeatherLogoSymbol.png")
                    SWLimg.thumbnail((size, size), Image.ANTIALIAS)
                    pil_im.paste(SWLimg, (bg_w - size, bg_h - size))
                    '''

                    # Save the image
                    '''
                    buf = StringIO()
                    pil_im.save(buf, format='JPEG')
                    frame = buf.getvalue()
                    '''

                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Length', len(frame))
                    self.send_header('Content-Type', 'image/jpeg')
                    self.end_headers()
                    self.wfile.write(output.frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logger.exception('Removed streaming client %s: %s', self.client_address, e)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    global logger
    global output

    formatter = logging.Formatter('[%(asctime)s] [%(filename)s] [%(lineno)d] [%(levelname)s] %(message)s')

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    with picamera.PiCamera(resolution='800x600', framerate=10) as camera:
        try:
            output = StreamingOutput()

            camera.rotation = 0
            camera.start_recording(output, format='mjpeg')

            streaming_server = StreamingServer(('0.0.0.0', 8000), StreamingHandler)
            streaming_server.serve_forever()
        finally:
            camera.stop_recording()


if __name__ == '__main__':
    main()

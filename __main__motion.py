import cv2
import datetime
import imutils
import numpy
import os
import picamera
import threading

from PIL import Image, ImageDraw, ImageFont

from camera import get_streaming_output, StreamingHandler, StreamingServer
from logger import get_logger

logger = get_logger()

first_frame = None
last_image_timestamp = datetime.datetime.utcnow()


def to_iso_format(date: datetime.datetime) -> str:
    if date.microsecond == 0:
        return '{}.000000'.format(date.isoformat())
    else:
        return date.isoformat()


def array_to_image(array):
    image = Image.fromarray(array)
    ImageDraw.Draw(image)

    return image


def draw_time(image):
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 25)
    my_text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    color = 'rgb(255,255,255)'
    text_size = font.getsize(my_text)
    button_size = (text_size[0] + 20, text_size[1] + 15)
    button_img = Image.new('RGBA', button_size, 'black')
    button_draw = ImageDraw.Draw(button_img)
    button_draw.text((10, 5), my_text, fill=color, font=font)
    image.paste(button_img, (0, 0))


def save_image(image):
    date = to_iso_format(datetime.datetime.utcnow())
    date = date.replace('-', '_')
    date = date.replace(':', '_')
    date = date.replace('.', '_')

    file_directory = '/home/pi/camera/images'
    file_name = 'frame_{}.jpg'.format(date)
    file_path = os.path.join(file_directory, file_name)

    if not os.path.exists(file_directory):
        os.makedirs(file_directory)

    cv2.imwrite(file_path, image)


def process_frame(frame):
    global first_frame
    global last_image_timestamp

    cv2.CV_LOAD_IMAGE_COLOR = 1
    numpyframe = numpy.frombuffer(frame, dtype=numpy.uint8)
    pil_frame = cv2.imdecode(numpyframe, cv2.CV_LOAD_IMAGE_COLOR)
    cv2_im_rgb = cv2.cvtColor(pil_frame, cv2.COLOR_BGR2RGB)

    gray = cv2.cvtColor(cv2_im_rgb, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    motion_detected = False

    if first_frame is not None:
        frame_delta = cv2.absdiff(first_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)

        for c in cnts:
            if cv2.contourArea(c) > 10:
                motion_detected = True
                break

            (x, y, w, h) = cv2.boundingRect(c)
            cv2.rectangle(cv2_im_rgb, (x, y), (x + w, y + h), (0, 255, 0), 2)

    first_frame = gray

    image = array_to_image(cv2_im_rgb)
    draw_time(image)

    if motion_detected:
        inverval = 60

        if (datetime.datetime.utcnow() - last_image_timestamp).total_seconds() > inverval:
            logger.debug('Motion detected more than %d seconds ago. Saving image', inverval)
            last_image_timestamp = datetime.datetime.utcnow()
            save_image(cv2_im_rgb)
        else:
            logger.debug('Motion detected less than %s seconds ago. Not saving image', inverval)

    return image


def server_worker(host, port):
    server = StreamingServer((host, port), StreamingHandler)
    server.serve_forever()


def main():
    resolution = '640x480'
    framerate = 10
    rotation = 0

    host = '0.0.0.0'
    port = 8000

    with picamera.PiCamera(resolution=resolution) as camera:
        try:
            streaming_output = get_streaming_output()

            camera.start_recording(streaming_output, format='mjpeg')
            camera.rotation = rotation

            worker = threading.Thread(target=server_worker, args=(host, port))
            worker.start()

            while True:
                with streaming_output.condition:
                    streaming_output.condition.wait()

                    # process_frame(streaming_output.frame)
        except Exception as e:
            logger.exception('Failed: %s', e)
        finally:
            worker.join()

            camera.stop_recording()


if __name__ == '__main__':
    main()

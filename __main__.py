import cv2
import datetime
import imutils
import io
import numpy
import os

from flask import Flask, render_template, Response
from pathlib import Path
from picamera import PiCamera
from picamera.array import PiRGBArray
from PIL import Image
from threading import Condition, Thread

import config

from logger import get_logger
from utils import to_file_name, to_iso_format


logger = get_logger()

app = Flask(__name__, template_folder=config.template_directory)

condition = Condition()

frame_current = None
frame_previous = None

last_motion_detected = datetime.datetime.utcnow() - datetime.timedelta(seconds=config.motion_save_interval)


def save_image_to_file(images, date):
    image_directory = os.path.join(
        config.motion_save_directory,
        '{:04d}'.format(date.year),
        '{:02d}'.format(date.month),
        '{:02d}'.format(date.day),
        '{:02d}'.format(date.hour)
    )

    if not os.path.exists(image_directory):
        os.makedirs(image_directory)

    for name, image in images.items():
        image_name = 'frame_{}_{}.jpg'.format(to_file_name(to_iso_format(date)), name)
        image_path = os.path.join(image_directory, image_name)

        logger.debug('Saving image to %s', image_path)

        cv2.imwrite(image_path, image)


def save_motion(images):
    global last_motion_detected

    now = datetime.datetime.utcnow()
    delta = (now - last_motion_detected).total_seconds()

    if delta > config.motion_save_interval:
        logger.debug('Motion detected %d seconds ago. Saving image...', delta)

        last_motion_detected = now

        save_image_to_file(images, now)
    else:
        logger.debug('Motion detected %d seconds ago. Not saving image', delta)


def process_frame(image):
    global frame_current
    global frame_previous

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    motion_detected = False

    if frame_previous is not None:
        delta = cv2.absdiff(frame_previous, gray)

        frame_current = numpy.concatenate((image, cv2.cvtColor(delta, cv2.COLOR_GRAY2BGR)), axis=1)

        thresh = cv2.threshold(delta, 12, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)

        for c in cnts:
            if cv2.contourArea(c) > 10:
                motion_detected = True

                x, y, w, h = cv2.boundingRect(c)
                cv2.rectangle(frame_current, (x, y), (x + w, y + h), (0, 255, 0), 2)

    frame_previous = gray

    if motion_detected:
        save_motion({'image': image})


def camera_worker():
    global frame_current

    try:
        logger.debug('Starting camera worker...')

        with PiCamera(resolution='{}x{}'.format(config.width, config.height)) as camera:
            array = PiRGBArray(camera, size=(config.width, config.height))

            for frame in camera.capture_continuous(array, format='bgr', use_video_port=True):
                with condition:
                    frame_current = cv2.cvtColor(frame.array, cv2.COLOR_BGR2RGB)

                    try:
                        process_frame(frame_current)
                    except Exception as e:
                        logger.exception('Failed to process frame: %s', e)

                    condition.notify_all()

                array.truncate(0)
    except Exception as e:
        logger.exception('Failed: %s', e)


def server_worker():
    try:
        logger.debug('Starting server worker...')

        app.run(host=config.host, port=config.port)
    except Exception as e:
        logger.exception('Failed: %s', e)


def frame_generator():
    try:
        while True:
            with condition:
                condition.wait()

                pil_im = Image.fromarray(frame_current)
                buf = io.BytesIO()
                pil_im.save(buf, format='JPEG')
                frame = buf.getvalue()

            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
    except Exception as e:
        logger.exception('Failed: %s', e)


@app.route('/')
def route_index():
    return render_template('index.html')


@app.route('/captured')
def route_captured():
    images = Path(config.motion_save_directory).rglob('*.jpg')
    images = [str(x).replace('{}/'.format(config.static_directory), '') for x in images]

    return render_template('captured.html', images=images)


@app.route('/stream')
def stream():
    return Response(frame_generator(), mimetype='multipart/x-mixed-replace; boundary=frame')


def main():
    try:
        logger.debug('Starting...')

        threads = [
            Thread(target=camera_worker),
            Thread(target=server_worker)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        logger.debug('Exiting...')


if __name__ == '__main__':
    main()

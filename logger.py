import logging


def get_logger():
    formatter = logging.Formatter('[%(asctime)s] [%(filename)s] [%(lineno)4d] [%(levelname)7s] %(message)s')

    ch = logging.StreamHandler()
    ch.setFormatter(formatter)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    return logger

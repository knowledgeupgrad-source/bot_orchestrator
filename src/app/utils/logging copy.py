import logging
import sys

from pythonjsonlogger import jsonlogger

from .settings import SETTINGS

def setup_logging():
    default_logger = logging.getLogger()
    default_logger.setLevel(SETTINGS.logging_level)

    logger = logging.getLogger(SETTINGS.app_name)
    logger.setLevel(SETTINGS.app_logging_level)

    # Use JSON logging for all other environments (dev, staging, prod)
    formatter = jsonlogger.JsonFormatter(
        fmt='%(levelname)s %(asctime)s %(name)s %(funcName)s %(lineno)d %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        json_default=str
    )
    #formatter = jsonlogger.JsonFormatter('%(levelname)s - %(asctime)s - %(name)s - %(funcName)s - %(lineno)s - %(message)s')
    log_handler = logging.StreamHandler(sys.stdout)
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)
    default_logger.addHandler(log_handler)

    # Prevent duplicate logs
    logger.propagate = False

    return logger

logger = setup_logging()

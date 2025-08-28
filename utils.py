import logging
import sys
import signal
import functools
import traceback


def setup_logger(name: str, level=logging.INFO) -> logging.Logger:
    """
    Create a standardized logger with timestamp, level, and name.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:  # prevent duplicate handlers
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger


def graceful_shutdown(consumer=None, producer=None, logger=None):
    """
    Register graceful shutdown for Kafka consumer/producer.
    Closes resources cleanly on SIGINT / SIGTERM.
    """
    def handle_sigterm(sig, frame):
        if logger:
            logger.info("Shutdown signal received, closing resources...")

        try:
            if consumer:
                consumer.close()
                if logger:
                    logger.info("Kafka consumer closed.")
            if producer:
                producer.flush()
                if logger:
                    logger.info("Kafka producer flushed & closed.")
        except Exception as e:
            if logger:
                logger.error(f"Error during shutdown: {e}")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)


def error_wrapper(func):
    """
    Decorator to wrap functions with try/except logging.
    Useful for handlers and DB calls.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = setup_logger(func.__module__)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Exception in {func.__name__}: {e}")
            logger.debug(traceback.format_exc())
            return None
    return wrapper
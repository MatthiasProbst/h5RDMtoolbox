from ._logger import logger, _file_handler, _stream_handler


def set_loglevel(level):
    """setting the logging level of sub-package h5wrapper"""
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)


__all__ = ['set_loglevel', ]

import logging
import sys
from typing import Optional
from pathlib import Path

_LOGGERS = {}
_LOG_LEVEL = logging.WARNING
_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: int = logging.WARNING,
    log_file: Optional[str] = None,
    console: bool = True
) -> None:
    
    global _LOG_LEVEL
    
    _LOG_LEVEL = level
    
    root_logger = logging.getLogger("pose_engine")
    root_logger.setLevel(level)
    
    root_logger.handlers.clear()
    
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    if not name.startswith("pose_engine"):
        name = f"pose_engine.{name}"
    
    if name not in _LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(_LOG_LEVEL)
        _LOGGERS[name] = logger
    
    return _LOGGERS[name]


def set_debug_mode(enabled: bool) -> None:
    
    global _LOG_LEVEL
    
    if enabled:
        _LOG_LEVEL = logging.DEBUG
        level_name = "DEBUG"
    else:
        _LOG_LEVEL = logging.WARNING
        level_name = "WARNING"
    
    for logger in _LOGGERS.values():
        logger.setLevel(_LOG_LEVEL)
    
    root_logger = logging.getLogger("pose_engine")
    root_logger.setLevel(_LOG_LEVEL)
    for handler in root_logger.handlers:
        handler.setLevel(_LOG_LEVEL)
    
    get_logger(__name__).info(f"Log level set to {level_name}")


setup_logging()

"""
Logger configuration for VibeSurf.
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from .common import get_workspace_dir


def setup_logger(name: str = "vibesurf") -> logging.Logger:
    """
    Set up and configure the logger for VibeSurf.
    
    Args:
        name (str): Logger name, defaults to "vibesurf"
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Get debug flag from environment variable
    debug_mode = os.getenv("VIBESURF_DEBUG", "false").lower() in ("true", "1", "yes", "on")
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Create formatter with file and line info
    if log_level == logging.DEBUG:
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Console handler - log to terminal
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler - log to file
    try:
        workspace_dir = get_workspace_dir()
        logs_dir = os.path.join(workspace_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Create log filename with current date
        current_date = datetime.now().strftime("%Y-%m-%d")
        log_filename = f"log_{current_date}.log"
        log_filepath = os.path.join(logs_dir, log_filename)
        
        # Use RotatingFileHandler to manage log file size
        file_handler = RotatingFileHandler(
            log_filepath,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # logger.info(f"Logger initialized. Log level: {logging.getLevelName(log_level)}")
        # logger.info(f"WorkSpace directory: {workspace_dir}")
        # logger.info(f"Log file: {log_filepath}")
        
    except Exception as e:
        logger.error(f"Failed to setup file logging: {e}")
        logger.warning("Continuing with console logging only")
    
    return logger


def get_logger(name: str = "vibesurf") -> logging.Logger:
    """
    Get or create a logger instance.
    
    Args:
        name (str): Logger name, defaults to "vibesurf"
        
    Returns:
        logging.Logger: Logger instance
    """
    return setup_logger(name)


# Create default logger instance
default_logger = get_logger()
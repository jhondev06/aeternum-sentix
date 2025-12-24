"""
Logging Configuration - Centralized logging setup for Sentix.

This module provides a standardized logging configuration with
structured formatting and file/console handlers.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_dir: str = "logs"
) -> logging.Logger:
    """
    Configure logging for the Sentix application.
    
    This function sets up:
    - Console handler with colored output
    - File handler (optional) with rotation
    - Structured log format with timestamps
    
    Args:
        level: Logging level (e.g., logging.INFO, logging.DEBUG).
        log_file: Optional filename for log file. If None, auto-generates.
        log_dir: Directory for log files.
        
    Returns:
        Configured root logger.
        
    Example:
        >>> from logging_config import setup_logging
        >>> logger = setup_logging(level=logging.DEBUG)
        >>> logger.info("Application started")
    """
    # Create log directory if needed
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    console_formatter = ColoredFormatter(
        "%(asctime)s │ %(levelname)-8s │ %(name)-20s │ %(message)s",
        datefmt="%H:%M:%S"
    )
    
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-30s | %(funcName)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file is None:
        log_file = f"sentix_{datetime.now().strftime('%Y%m%d')}.log"
    
    file_path = log_path / log_file
    file_handler = logging.FileHandler(file_path, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('transformers').setLevel(logging.WARNING)
    logging.getLogger('yfinance').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    root_logger.info(f"Logging initialized. Level: {logging.getLevelName(level)}, File: {file_path}")
    
    return root_logger


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter with color support for console output.
    
    Colors are applied based on log level for better visibility.
    """
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[41m',   # Red background
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors."""
        # Save original levelname
        original_levelname = record.levelname
        
        # Check if terminal supports colors
        if sys.stdout.isatty():
            color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
            record.levelname = f"{color}{record.levelname}{reset}"
        
        # Format the record
        result = super().format(record)
        
        # Restore original levelname
        record.levelname = original_levelname
        
        return result


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    This is a convenience function that returns a child logger
    of the root logger configured by setup_logging.
    
    Args:
        name: Logger name (typically __name__).
        
    Returns:
        Logger instance.
        
    Example:
        >>> from logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    return logging.getLogger(name)


# Pre-configured loggers for common modules
def get_ingest_logger() -> logging.Logger:
    """Get logger for ingest modules."""
    return logging.getLogger('sentix.ingest')


def get_sentiment_logger() -> logging.Logger:
    """Get logger for sentiment modules."""
    return logging.getLogger('sentix.sentiment')


def get_model_logger() -> logging.Logger:
    """Get logger for model modules."""
    return logging.getLogger('sentix.model')


def get_api_logger() -> logging.Logger:
    """Get logger for API modules."""
    return logging.getLogger('sentix.api')

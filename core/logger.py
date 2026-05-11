"""Logging configuration and utilities."""

import logging
import logging.config
import json
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


class DeprecationFilter(logging.Filter):
    """Filter to suppress specific deprecation warnings from dependencies."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Suppress known deprecation warnings that are not actionable.
        
        - db.index.vector.queryNodes: LangChain limitation (awaiting update)
        - elementId deprecation notices: Using modern Neo4j API
        """
        if record.levelname == "WARNING" and "neo4j.notifications" in record.name:
            # Suppress queryNodes deprecation (LangChain's responsibility to update)
            if "db.index.vector.queryNodes is deprecated" in record.getMessage():
                return False
            # Suppress other known Neo4j deprecation notices that aren't actionable
            if "DEPRECATION" in record.getMessage() and "replaced by" in record.getMessage():
                return False
        return True


def setup_logging(log_level: str = "INFO", log_format: str = "standard") -> None:
    """Configure logging for the application."""

    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Define log format
    if log_format == "json":
        log_format_str = (
            "%(asctime)s %(name)s %(levelname)s %(filename)s:%(lineno)d - %(message)s"
        )
    else:
        log_format_str = (
            "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
        )

    # Configure logging
    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": log_format_str,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "verbose": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "filters": {
            "deprecation_filter": {
                "()": DeprecationFilter,
            },
        },
        "handlers": {
            "console": {
                "level": log_level,
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
                "filters": ["deprecation_filter"],
            },
            "file": {
                "level": log_level,
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "verbose",
                "filename": logs_dir / "chatbot.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "filters": ["deprecation_filter"],
            },
            "error_file": {
                "level": "ERROR",
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "verbose",
                "filename": logs_dir / "error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "filters": ["deprecation_filter"],
            },
        },
        "loggers": {
            "uvicorn": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "fastapi": {
                "level": log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "neo4j.notifications": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
                "filters": ["deprecation_filter"],
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file", "error_file"],
        },
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)

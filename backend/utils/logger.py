"""
Logging configuration for ResearchAgent.

Uses loguru for structured logging with console and file output.
"""

import sys
from pathlib import Path

from loguru import logger

from backend.utils.config import settings


def setup_logger() -> None:
    """Configure the application logger."""
    # Remove default handler
    logger.remove()

    # Console handler with color
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )

    # File handler for all logs
    log_dir = settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        str(log_dir / "research_agent_{time:YYYY-MM-DD}.log"),
        rotation="1 day",
        retention="30 days",
        compression="zip",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    # Error file handler
    logger.add(
        str(log_dir / "errors_{time:YYYY-MM-DD}.log"),
        rotation="1 day",
        retention="90 days",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


def get_logger(name: str = "research_agent"):
    """Get a named logger instance."""
    return logger.bind(module=name)


# Initialize logger on import
setup_logger()

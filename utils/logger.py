"""
Logging Utility for Gojo Discord Bot
Sets up logging to both console and file
"""

import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "gojo") -> logging.Logger:
    """
    Set up and return a logger that writes to both console and file.

    Args:
        name: The name for the logger (default: "gojo")

    Returns:
        A configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture all levels

    # Prevent adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Log file path
    log_file = log_dir / "bot.log"

    # Create formatters
    # Detailed format for file logging
    file_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Simpler format for console
    console_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # File handler - writes everything to bot.log
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # Console handler - only INFO and above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Create a default logger instance for easy importing
logger = setup_logger()


def log_command(user: str, user_id: int, command: str, guild: str = None):
    """
    Log when a user uses a command.

    Args:
        user: The username who used the command
        user_id: The user's Discord ID
        command: The command that was used
        guild: The server name (optional)
    """
    location = f"in {guild}" if guild else "in DMs"
    logger.info(f"Command /{command} used by {user} (ID: {user_id}) {location}")

    # Track commands_used for achievements
    try:
        from utils.achievements_data import update_user_stat, check_and_complete_achievements
        update_user_stat(user_id, "commands_used", increment=1)
        check_and_complete_achievements(user_id)
    except:
        pass


def log_error(error: Exception, context: str = None):
    """
    Log an error with optional context.

    Args:
        error: The exception that occurred
        context: Additional context about what was happening
    """
    if context:
        logger.error(f"{context}: {type(error).__name__}: {error}")
    else:
        logger.error(f"{type(error).__name__}: {error}")


def log_startup():
    """Log a startup message with timestamp"""
    logger.info("=" * 50)
    logger.info("Gojo Bot Starting Up...")
    logger.info(f"Startup time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)


def log_shutdown():
    """Log a shutdown message"""
    logger.info("=" * 50)
    logger.info("Gojo Bot Shutting Down...")
    logger.info("=" * 50)

"""
logger.py — Unified logging for USD/JPY Bot
============================================
Writes to both console and logs/bot.log
"""

import os
import logging
from datetime import datetime

import settings as cfg

os.makedirs(cfg.LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(cfg.BOT_LOG),
        logging.StreamHandler(),
    ],
)

_log = logging.getLogger("jpyusd_bot")

def info(msg):    _log.info(msg)
def warning(msg): _log.warning(msg)
def error(msg):   _log.error(msg)
def debug(msg):   _log.debug(msg)

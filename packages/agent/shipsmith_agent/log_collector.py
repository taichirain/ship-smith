import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class LogCollector:
    def __init__(self, send_callback: Callable[[int, str, str], bool]):
        self.send_callback = send_callback
        self.seq = 0

    def emit(self, phase: str, content: str) -> bool:
        lines = content.split("\n")
        for line in lines:
            if line.strip():
                logger.info(f"[{phase}] {line}")

        success = self.send_callback(self.seq, phase, content)
        self.seq += 1
        return success

    def info(self, phase: str, message: str):
        self.emit(phase, message)

    def error(self, phase: str, message: str):
        logger.error(f"[{phase}] {message}")
        self.emit(phase, message)

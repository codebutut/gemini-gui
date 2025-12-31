import threading
import time
from datetime import datetime
from typing import Optional

class RateLimiter:
    """
    A thread-safe Token Bucket rate limiter.
    """
    def __init__(self, max_requests: int, period: float, auto_refill: bool = False):
        """
        Initializes the RateLimiter.

        Args:
            max_requests (int): Maximum number of tokens (requests) allowed.
            period (float): The time period in seconds for the rate limit.
            auto_refill (bool): If True, starts a background timer to refill tokens.
        """
        self.max_requests = max_requests
        self.period = period
        self.tokens = max_requests
        self.lock = threading.Lock()
        self.auto_refill = auto_refill
        
        # Calculate refill rate
        self.refill_interval = self.period / self.max_requests

        if self.auto_refill:
            self._start_refill_timer()

    def _start_refill_timer(self) -> None:
        """Starts the background refill timer."""
        timer = threading.Timer(self.refill_interval, self._refill_token)
        timer.daemon = True
        timer.start()

    def _refill_token(self) -> None:
        """Adds a token back to the bucket."""
        with self.lock:
            if self.tokens < self.max_requests:
                self.tokens += 1
        self._start_refill_timer()

    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Attempts to acquire a token.

        Args:
            blocking (bool): Whether to block and wait for a token.
            timeout (Optional[float]): Max time to wait if blocking.

        Returns:
            bool: True if token acquired, False otherwise.
        """
        start_time = time.monotonic()
        while True:
            with self.lock:
                if self.tokens > 0:
                    self.tokens -= 1
                    return True
            
            if not blocking:
                return False
            
            if timeout is not None and time.monotonic() - start_time >= timeout:
                return False
            
            time.sleep(0.1)

    def release(self) -> None:
        """Manually releases a token back to the pool."""
        with self.lock:
            self.tokens = min(self.tokens + 1, self.max_requests)

    def remaining(self) -> int:
        """Returns the number of remaining tokens."""
        with self.lock:
            return self.tokens
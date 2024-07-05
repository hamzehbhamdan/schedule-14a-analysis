import time

class RateLimiter:
    def __init__(self, rate_limit, period):
        self.rate_limit = rate_limit
        self.period = period
        self.timestamps = []

    def wait(self):
        # Remove timestamps outside the current period
        now = time.time()
        self.timestamps = [timestamp for timestamp in self.timestamps if now - timestamp < self.period]
        
        # Wait if the rate limit is reached
        if len(self.timestamps) >= self.rate_limit:
            time_to_wait = self.period - (now - self.timestamps[0])
            time.sleep(time_to_wait)
            
        # Add a new timestamp for the current request
        self.timestamps.append(time.time())
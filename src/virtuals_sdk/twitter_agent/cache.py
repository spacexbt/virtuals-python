from typing import Dict, Any, Optional
from functools import lru_cache
import time

class ResultCache:
    def __init__(self, max_size: int = 128, ttl: int = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if time.time() - entry['timestamp'] > self.ttl:
            del self.cache[key]
            return None
            
        return entry['value']

    def set(self, key: str, value: Any) -> None:
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest = min(self.cache.items(), key=lambda x: x[1]['timestamp'])[0]
            del self.cache[oldest]

        self.cache[key] = {
            'value': value,
            'timestamp': time.time()
        }
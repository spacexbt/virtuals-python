class RateLimitError(Exception):
    """Custom exception for API rate limit errors"""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds")

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass
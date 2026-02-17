"""
Retry handler with exponential backoff and error classification.
Handles API timeouts, rate limits, and service errors gracefully.
"""

import time
import re
from enum import Enum
from typing import Callable, Optional, Any, Tuple
from dataclasses import dataclass


class ErrorType(Enum):
    """Classification of error types for retry decisions."""
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVICE_ERROR = "service_error"
    INVALID_REQUEST = "invalid_request"
    AUTHENTICATION = "authentication"
    OTHER = "other"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    backoff_multiplier: float = 2.0
    allowed_exceptions: Optional[Tuple] = None  # Tuple of exception types to retry on validation errors


def classify_error(exception: Exception) -> ErrorType:
    """
    Classify exception to determine appropriate retry strategy.
    
    Args:
        exception: The exception to classify
    
    Returns:
        ErrorType enum indicating the error category
    """
    if exception is None:
        return ErrorType.OTHER
    
    msg = str(exception).lower()
    exc_type = type(exception).__name__.lower()
    
    # Timeout patterns
    if any(pattern in msg for pattern in ["timeout", "timed out", "deadline", "408"]):
        return ErrorType.TIMEOUT
    
    if any(pattern in exc_type for pattern in ["timeout", "deadline"]):
        return ErrorType.TIMEOUT
    
    # Rate limit patterns
    if any(pattern in msg for pattern in ["rate limit", "429", "too many requests", "quota"]):
        return ErrorType.RATE_LIMIT
    
    # Service error patterns (retryable)
    if any(pattern in msg for pattern in ["503", "502", "500", "overloaded", "unavailable", "busy"]):
        return ErrorType.SERVICE_ERROR
    
    # Authentication/authorization (non-retryable)
    if any(pattern in msg for pattern in ["401", "403", "unauthorized", "forbidden", "invalid api", "authentication"]):
        return ErrorType.AUTHENTICATION
    
    # Invalid request (non-retryable)
    if any(pattern in msg for pattern in ["400", "invalid", "malformed", "bad request"]):
        return ErrorType.INVALID_REQUEST
    
    return ErrorType.OTHER


def should_retry(error_type: ErrorType, attempt: int, max_retries: int) -> bool:
    """
    Determine if an error should trigger a retry.
    
    Args:
        error_type: Classification of the error
        attempt: Current attempt number (0-indexed)
        max_retries: Maximum number of retries allowed
    
    Returns:
        True if should retry, False if should give up
    """
    if attempt >= max_retries:
        return False
    
    # These error types are retryable
    if error_type in [ErrorType.TIMEOUT, ErrorType.RATE_LIMIT, ErrorType.SERVICE_ERROR]:
        return True
    
    # Non-retryable errors
    if error_type in [ErrorType.AUTHENTICATION, ErrorType.INVALID_REQUEST]:
        return False
    
    # Other errors: retry once
    return attempt == 0


def calculate_backoff_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate exponential backoff delay with jitter.
    
    Args:
        attempt: Current attempt number (0-indexed)
        config: RetryConfig with backoff parameters
    
    Returns:
        Delay in seconds before next retry
    """
    # Exponential backoff: base_delay * (multiplier ^ attempt)
    delay = config.base_delay * (config.backoff_multiplier ** attempt)
    
    # Cap at max_delay
    delay = min(delay, config.max_delay)
    
    # Add small random jitter to prevent thundering herd
    import random
    jitter = random.uniform(0, delay * 0.1)  # 0-10% jitter
    
    return delay + jitter


def call_with_retry(
    func: Callable,
    config: RetryConfig = None,
    error_callback: Optional[Callable] = None,
    log_prefix: str = ""
) -> Optional[Any]:
    """
    Call function with exponential backoff retry and error classification.
    
    Args:
        func: Function to call (should raise Exception on failure)
        config: RetryConfig with retry parameters (default: 3 retries)
        error_callback: Optional callback called on each error with
                       (attempt_num, error_type, exception)
        log_prefix: String prefix for log messages (e.g., "Model X")
    
    Returns:
        Result from func if successful, or None if all retries exhausted
    
    Example:
        def _call():
            return some_api_call()
        
        result = call_with_retry(
            _call,
            config=RetryConfig(max_retries=3, base_delay=2.0),
            error_callback=lambda attempt, error_type, exc: 
                print(f"Attempt {attempt}: {error_type.value}")
        )
    """
    if config is None:
        config = RetryConfig()
    
    last_exception = None
    
    for attempt in range(config.max_retries + 1):
        try:
            return func()
        
        except Exception as e:
            last_exception = e
            error_type = classify_error(e)
            
            # Check if this exception type should trigger retry (for validation failures)
            if config.allowed_exceptions and isinstance(e, config.allowed_exceptions):
                # This is a validation error that can be retried
                pass
            
            # Log this attempt's failure
            if error_callback:
                error_callback(attempt + 1, error_type, e)
            
            # Check if we should retry
            if not should_retry(error_type, attempt, config.max_retries):
                if error_type == ErrorType.AUTHENTICATION:
                    print(f"{log_prefix} Auth error (non-retryable): {str(e)[:100]}")
                elif error_type == ErrorType.INVALID_REQUEST:
                    print(f"{log_prefix} Invalid request (non-retryable): {str(e)[:100]}")
                else:
                    print(f"{log_prefix} Error (non-retryable): {error_type.value}")
                return None
            
            # We will retry
            if attempt < config.max_retries:
                delay = calculate_backoff_delay(attempt, config)
                print(f"{log_prefix} {error_type.value} on attempt {attempt + 1}/{config.max_retries + 1}. "
                      f"Retrying in {delay:.1f}s...")
                time.sleep(delay)
            else:
                print(f"{log_prefix} All {config.max_retries + 1} retries exhausted. Final error: {error_type.value}")
                return None
    
    return None


class RetryableCall:
    """
    Context manager for tracking retry statistics.
    
    Example:
        with RetryableCall("Model X Concept Y") as call:
            result = call.execute(my_function, config=RetryConfig())
            if call.failed:
                log_error(call.error_type, call.attempts)
    """
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.attempts = 0
        self.failed = False
        self.error_type = None
        self.exception = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def execute(self, func: Callable, config: RetryConfig = None) -> Optional[Any]:
        """Execute function with retry logic."""
        if config is None:
            config = RetryConfig()
        
        def _callback(attempt, error_type, exception):
            self.attempts = attempt
            self.error_type = error_type
            self.exception = exception
        
        result = call_with_retry(
            func,
            config,
            error_callback=_callback,
            log_prefix=f"[{self.operation_name}]"
        )
        
        self.failed = result is None
        return result
"""
Retry handler for API calls with exponential backoff.
"""
import time
import logging
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0   # seconds

def call_with_retry(api_call, config: RetryConfig, log_prefix=""):
    """
    Calls a function with retry logic.
    
    :param api_call: The function to call.
    :param config: A RetryConfig object.
    :param log_prefix: A prefix for log messages.
    :return: The result of the api_call.
    """
    retries = 0
    while True:
        try:
            return api_call()
        except Exception as e:
            retries += 1
            if retries > config.max_retries:
                logging.error(f"{log_prefix} Final attempt failed. Error: {e}")
                raise e

            delay = min(config.max_delay, config.base_delay * (2 ** (retries - 1)))
            logging.warning(f"{log_prefix} Attempt {retries}/{config.max_retries} failed with error: {e}. Retrying in {delay:.2f} seconds...")
            time.sleep(delay)

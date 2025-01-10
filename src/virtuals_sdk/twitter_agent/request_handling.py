import aiohttp
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from string import Template
from .exceptions import RateLimitError

logger = logging.getLogger(__name__)

class RequestHandler:
    @staticmethod
    def interpolate_template(template_str: str, values: Dict[str, Any]) -> str:
        python_style = template_str.replace('{{', '$').replace('}}', '')
        return Template(python_style).safe_substitute(values)

    @staticmethod
    async def make_request(config: Dict[str, Any], retry_attempts: int = 3, retry_delay: int = 1) -> Any:
        retry_count = 0

        while retry_count < retry_attempts:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(**config) as response:
                        if response.status == 429:
                            retry_after = int(response.headers.get('Retry-After', 60))
                            raise RateLimitError(retry_after)
                        
                        response.raise_for_status()
                        return await response.json()

            except RateLimitError as e:
                logger.warning(f"Rate limit hit: {e}")
                await asyncio.sleep(e.retry_after)
                retry_count += 1
                continue
                
            except aiohttp.ClientError as e:
                error_msg = str(e)
                if retry_count < retry_attempts - 1:
                    wait_time = retry_delay * (2 ** retry_count)
                    logger.warning(f"Request failed: {error_msg}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    retry_count += 1
                    continue
                raise

        raise Exception("Max retry attempts reached")
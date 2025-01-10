from typing import List, Any, Dict, Optional, Union, Set, TypeVar, Generic
from dataclasses import dataclass, asdict, field
from string import Template
import json
import uuid
import asyncio
import logging
import aiohttp
from functools import lru_cache

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

T = TypeVar('T')

class RateLimitError(Exception):
    """Custom exception for API rate limit errors"""
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds")

@dataclass
class FunctionArgument:
    name: str
    description: str
    type: str
    id: str = None
    required: bool = True
    
    def __post_init__(self):
        self.id = self.id or str(uuid.uuid4())

@dataclass
class FunctionConfig:
    method: str = "get"
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)
    success_feedback: str = ""
    error_feedback: str = ""
    isMainLoop: bool = False
    isReaction: bool = False
    headersString: str = "{}"
    payloadString: str = "{}"
    platform: Optional[str] = None
    retry_attempts: int = 3
    retry_delay: int = 1

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.payload is None:
            self.payload = {}

        self.headersString = json.dumps(self.headers, indent=4)
        self.payloadString = json.dumps(self.payload, indent=4)

@dataclass
class Function:
    fn_name: str
    fn_description: str
    args: List[FunctionArgument]
    config: FunctionConfig
    hint: str = ""
    id: str = None
    cached_results: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.id = self.id or str(uuid.uuid4())

    def toJson(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "fn_name": self.fn_name,
            "fn_description": self.fn_description,
            "args": [asdict(arg) for arg in self.args],
            "hint": self.hint,
            "config": asdict(self.config)
        }

    def _validate_args(self, *args) -> Dict[str, Any]:
        """Validate and convert positional arguments to named arguments"""
        required_args = [arg for arg in self.args if arg.required]
        if len(args) < len(required_args):
            raise ValueError(
                f"Expected at least {len(required_args)} arguments, got {len(args)}"
            )

        # Create dictionary of argument name to value
        arg_dict = {}
        for provided_value, arg_def in zip(args, self.args):
            # Skip optional arguments that weren't provided
            if provided_value is None and not arg_def.required:
                continue

            arg_dict[arg_def.name] = provided_value

            # Enhanced type validation
            if arg_def.type == "string" and not isinstance(provided_value, str):
                raise TypeError(f"Argument {arg_def.name} must be a string")
            elif arg_def.type == "array" and not isinstance(provided_value, (list, tuple)):
                raise TypeError(f"Argument {arg_def.name} must be an array")
            elif arg_def.type == "number" and not isinstance(provided_value, (int, float)):
                raise TypeError(f"Argument {arg_def.name} must be a number")
            elif arg_def.type == "boolean" and not isinstance(provided_value, bool):
                raise TypeError(f"Argument {arg_def.name} must be a boolean")

        return arg_dict

    def _interpolate_template(self, template_str: str, values: Dict[str, Any]) -> str:
        """Interpolate a template string with given values"""
        python_style = template_str.replace('{{', '$').replace('}}', '')
        return Template(python_style).safe_substitute(values)

    def _prepare_request(self, arg_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare the request configuration with interpolated values"""
        config = self.config

        # Interpolate URL
        url = self._interpolate_template(config.url, arg_dict)

        # Interpolate payload with improved handling of complex types
        payload = {}
        for key, value in config.payload.items():
            template_key = self._interpolate_template(key, arg_dict)
            if isinstance(value, str):
                if value.strip('{}') in arg_dict:
                    payload[template_key] = arg_dict[value.strip('{}')]
                else:
                    payload[template_key] = self._interpolate_template(value, arg_dict)
            elif isinstance(value, (dict, list)):
                # Handle nested structures
                payload[template_key] = self._interpolate_nested_structure(value, arg_dict)
            else:
                payload[template_key] = value

        return {
            "method": config.method,
            "url": url,
            "headers": config.headers,
            "data": json.dumps(payload)
        }

    def _interpolate_nested_structure(self, value: Union[Dict, List], arg_dict: Dict[str, Any]) -> Any:
        """Recursively interpolate nested structures"""
        if isinstance(value, dict):
            return {
                self._interpolate_template(k, arg_dict): 
                self._interpolate_nested_structure(v, arg_dict)
                for k, v in value.items()
            }
        elif isinstance(value, list):
            return [self._interpolate_nested_structure(item, arg_dict) for item in value]
        elif isinstance(value, str):
            return self._interpolate_template(value, arg_dict)
        return value

    @lru_cache(maxsize=128)
    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """Get cached result if available"""
        return self.cached_results.get(cache_key)

    async def __call__(self, *args) -> Any:
        """Allow the function to be called directly with arguments"""
        arg_dict = self._validate_args(*args)
        cache_key = json.dumps(arg_dict, sort_keys=True)
        
        # Check cache first
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for {self.fn_name} with args {cache_key}")
            return cached_result

        request_config = self._prepare_request(arg_dict)
        retry_count = 0

        while retry_count < self.config.retry_attempts:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(**request_config) as response:
                        if response.status == 429:  # Rate limit
                            retry_after = int(response.headers.get('Retry-After', 60))
                            raise RateLimitError(retry_after)
                        
                        response.raise_for_status()
                        result = await response.json()
                        
                        # Cache successful result
                        self.cached_results[cache_key] = result
                        
                        if self.config.success_feedback:
                            logger.info(self._interpolate_template(
                                self.config.success_feedback,
                                {"response": result, **arg_dict}
                            ))
                        return result

            except RateLimitError as e:
                logger.warning(f"Rate limit hit: {e}")
                await asyncio.sleep(e.retry_after)
                retry_count += 1
                continue
                
            except aiohttp.ClientError as e:
                error_msg = str(e)
                if retry_count < self.config.retry_attempts - 1:
                    wait_time = self.config.retry_delay * (2 ** retry_count)  # Exponential backoff
                    logger.warning(f"Request failed: {error_msg}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    retry_count += 1
                    continue
                else:
                    if self.config.error_feedback:
                        logger.error(self._interpolate_template(
                            self.config.error_feedback,
                            {"response": {"error": error_msg}, **arg_dict}
                        ))
                    raise
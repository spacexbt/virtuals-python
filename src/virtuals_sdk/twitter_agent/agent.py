import logging
import time
from typing import List, Dict, Any, Optional
from .models import Function, FunctionConfig, FunctionArgument
from .cache import ResultCache
from .exceptions import ValidationError, ConfigurationError
from virtuals_sdk.twitter_agent import sdk

logger = logging.getLogger(__name__)

class Agent:
    def __init__(
        self,
        api_key: str,
        goal: str = "",
        description: str = "",
        world_info: str = "",
        main_heartbeat: int = 15,
        reaction_heartbeat: int = 5,
        config_cache_ttl: int = 3600
    ):
        self.game_sdk = sdk.GameSDK(api_key)
        self._validate_heartbeats(main_heartbeat, reaction_heartbeat)
        
        self.goal = goal
        self.description = description
        self.world_info = world_info
        self.enabled_functions: List[str] = []
        self.custom_functions: List[Function] = []
        self.main_heartbeat = main_heartbeat
        self.reaction_heartbeat = reaction_heartbeat
        
        self.result_cache = ResultCache(ttl=config_cache_ttl)
        self._last_config_validation = 0
        self._config_valid = False

    def _validate_heartbeats(self, main_heartbeat: int, reaction_heartbeat: int) -> None:
        if not isinstance(main_heartbeat, int) or main_heartbeat < 1:
            raise ValidationError("main_heartbeat must be a positive integer")
        if not isinstance(reaction_heartbeat, int) or reaction_heartbeat < 1:
            raise ValidationError("reaction_heartbeat must be a positive integer")
        if reaction_heartbeat >= main_heartbeat:
            raise ValidationError("reaction_heartbeat must be less than main_heartbeat")

    def _validate_configuration(self) -> bool:
        if not self.goal:
            logger.warning("Agent goal is not set")
            return False
            
        if not self.description:
            logger.warning("Agent description is not set")
            return False

        seen_functions = set()
        for func in self.custom_functions:
            if func.fn_name in seen_functions:
                logger.error(f"Duplicate function name: {func.fn_name}")
                return False
            seen_functions.add(func.fn_name)

        return True

    async def simulate_twitter(self, session_id: str):
        if not self._validate_configuration():
            raise ConfigurationError("Invalid agent configuration")

        return await self.game_sdk.simulate(
            session_id,
            self.goal,
            self.description,
            self.world_info,
            self.enabled_functions,
            self.custom_functions
        )

    async def react(self, session_id: str, platform: str, tweet_id: str = None, event: str = None, task: str = None):
        if not self._validate_configuration():
            raise ConfigurationError("Invalid agent configuration")

        return await self.game_sdk.react(
            session_id=session_id,
            platform=platform,
            event=event,
            task=task,
            tweet_id=tweet_id,
            goal=self.goal,
            description=self.description,
            world_info=self.world_info,
            functions=self.enabled_functions,
            custom_functions=self.custom_functions
        )

    async def deploy_twitter(self):
        if not self._validate_configuration():
            raise ConfigurationError("Invalid agent configuration")

        return await self.game_sdk.deploy(
            self.goal,
            self.description,
            self.world_info,
            self.enabled_functions,
            self.custom_functions,
            self.main_heartbeat,
            self.reaction_heartbeat
        )
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import uuid
import json

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
    platform: Optional[str] = None
    retry_attempts: int = 3
    retry_delay: int = 1

    def __post_init__(self):
        self.headers = self.headers or {}
        self.payload = self.payload or {}
        self.headersString = json.dumps(self.headers, indent=4)
        self.payloadString = json.dumps(self.payload, indent=4)
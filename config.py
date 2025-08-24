import yaml
import os
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from pathlib import Path


class FailureCondition(BaseModel):
    method: Optional[str] = None
    count: Optional[int] = None
    every: Optional[int] = None
    probability: Optional[float] = None
    delay: Optional[int] = None


class FailureResponse(BaseModel):
    status_code: int
    body: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None


class FailureRule(BaseModel):
    condition: FailureCondition
    response: FailureResponse


class Endpoint(BaseModel):
    path: str
    methods: List[str]
    debug: bool = False
    failure_rules: List[FailureRule] = []


class Target(BaseModel):
    url: str
    headers: Optional[Dict[str, str]] = None
    endpoints: List[Endpoint] = []


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class ProxyConfig(BaseModel):
    server: ServerConfig
    logging: LoggingConfig
    targets: Dict[str, Target]


def load_config(config_path: str = "config.yaml") -> ProxyConfig:
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file {config_path} not found")

    with open(config_file, 'r') as f:
        config_data = yaml.safe_load(f)

    # Expand environment variables in headers
    for target_name, target_data in config_data.get('targets', {}).items():
        if 'headers' in target_data:
            for key, value in target_data['headers'].items():
                if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                    env_var = value[2:-1]
                    target_data['headers'][key] = os.getenv(env_var, value)

    return ProxyConfig(**config_data)
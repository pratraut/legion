import yaml
import os
import logging
from typing import Dict, Any
from jsonschema import validate
from src.config.schema import CONFIG_SCHEMA

class Config:
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self.logger = logging.getLogger("Config")
            self.load_config()
    
    def load_config(self):
        """Load configuration from main config file."""
        # Load main config
        config_path = os.getenv('R4DAR_CONFIG', 'config.yml')
        try:
            with open(config_path, 'r') as f:
                try:
                    self._config = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid configuration: YAML parsing error - {str(e)}")
                
            if not isinstance(self._config, dict):
                raise ValueError("Invalid configuration: Root must be a dictionary")
                
            # Validate against schema
            try:
                validate(instance=self._config, schema=CONFIG_SCHEMA)
            except Exception as e:
                raise ValueError(f"Invalid configuration: Schema validation failed - {str(e)}")
                
        except FileNotFoundError:
            raise ValueError(f"Invalid configuration: Config file not found at {config_path}")
        except Exception as e:
            if not isinstance(e, ValueError):
                raise ValueError(f"Invalid configuration: {str(e)}")
            raise
            
    def load_extension_config(self, config_path: str) -> None:
        """Load and merge configuration from an extension's config file.
        
        Args:
            config_path: Path to the extension's config file
        """
        try:
            with open(config_path, 'r') as f:
                try:
                    extension_config = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    self.logger.error(f"Failed to parse extension config {config_path}: {e}")
                    return
                    
                if extension_config:
                    self.logger.info(f"Loaded extension configuration from {config_path}")
                    # Deep merge extension config into main config
                    self._merge_configs(self._config, extension_config)
                    
        except Exception as e:
            self.logger.error(f"Failed to load extension config {config_path}: {e}")
    
    def _merge_configs(self, base: Dict, update: Dict) -> None:
        """Deep merge update dict into base dict."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                # Recursively merge nested dicts
                self._merge_configs(base[key], value)
            else:
                # Update or add new value
                base[key] = value
    
    @property
    def database_url(self) -> str:
        """Get database connection URL."""
        db = self._config['database']
        return f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"
    
    @property
    def etherscan_api_key(self) -> str:
        """Get Etherscan API key."""
        return self._config.get('block_explorers', {}).get('etherscan', {}).get('key')
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        if '.' in key:
            # Handle nested keys
            keys = key.split('.')
            value = self._config
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    value = None
                if value is None:
                    break
            return value if value is not None else default
            
        return self._config.get(key, default)
    
    @property
    def data_dir(self) -> str:
        """Get the data directory path"""
        return self._config.get('data_dir')
    
    @property
    def openai_api_key(self) -> str:
        """Get OpenAI API key"""
        key = self._config.get('llm', {}).get('openai', {}).get('key')
        if not key:
            raise ValueError("OpenAI API key not configured")
        return key
    
    @property
    def openai_model(self) -> str:
        """Get OpenAI model to use"""
        return self._config.get('llm', {}).get('openai', {}).get('model', 'gpt-4')
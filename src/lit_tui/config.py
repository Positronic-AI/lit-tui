"""
Configuration management for LIT TUI.

This module handles loading, saving, and validating configuration settings.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


logger = logging.getLogger(__name__)


class OllamaConfig(BaseModel):
    """Ollama service configuration."""
    host: str = Field(default="http://localhost:11434", description="Ollama server URL")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    default_model: Optional[str] = Field(default=None, description="Default model to use")


class UIConfig(BaseModel):
    """User interface configuration."""
    theme: str = Field(default="dark", description="UI theme (dark/light/auto)")
    show_token_count: bool = Field(default=True, description="Show token count in UI")
    auto_scroll: bool = Field(default=True, description="Auto-scroll to new messages")
    show_timestamps: bool = Field(default=True, description="Show message timestamps")
    
    @validator('theme')
    def validate_theme(cls, v):
        if v not in ['dark', 'light', 'auto']:
            raise ValueError('theme must be one of: dark, light, auto')
        return v


class StorageConfig(BaseModel):
    """Storage and session configuration."""
    max_sessions: int = Field(default=100, description="Maximum number of stored sessions")
    auto_save: bool = Field(default=True, description="Automatically save sessions")
    session_timeout_days: int = Field(default=30, description="Days before old sessions expire")


class MCPServerConfig(BaseModel):
    """MCP server configuration."""
    name: str = Field(description="Server name")
    command: str = Field(description="Command to start the server")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    timeout: int = Field(default=10, description="Connection timeout in seconds")


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) configuration."""
    enabled: bool = Field(default=True, description="Enable MCP integration")
    servers: List[MCPServerConfig] = Field(default_factory=list, description="MCP servers")
    timeout: int = Field(default=5, description="Default MCP operation timeout")


class Config(BaseModel):
    """Main configuration model."""
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    debug: bool = Field(default=False, description="Enable debug logging")
    
    class Config:
        extra = "allow"  # Allow additional fields for extensibility


def get_default_config() -> Config:
    """Get default configuration with some example MCP servers."""
    config = Config()
    
    # Add some example MCP server configurations
    # These are commented out by default - users can enable them
    example_servers = [
        {
            "name": "filesystem",
            "command": "mcp-server-filesystem",
            "args": ["--root", str(Path.home())],
            "enabled": False
        },
        {
            "name": "git", 
            "command": "mcp-server-git",
            "args": [],
            "enabled": False
        }
    ]
    
    return config


async def load_config(config_dir: Path) -> Config:
    """Load configuration from directory."""
    config_file = config_dir / "config.json"
    
    # Create config directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            config = Config(**config_data)
            logger.info(f"Loaded configuration from {config_file}")
        except Exception as e:
            logger.warning(f"Failed to load config from {config_file}: {e}")
            logger.info("Using default configuration")
            config = get_default_config()
    else:
        logger.info("No config file found, creating default configuration")
        config = get_default_config()
        await save_config(config, config_dir)
    
    return config


async def save_config(config: Config, config_dir: Path) -> None:
    """Save configuration to directory."""
    config_file = config_dir / "config.json"
    
    try:
        # Create config directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(config.dict(), f, indent=2)
        logger.info(f"Saved configuration to {config_file}")
    except Exception as e:
        logger.error(f"Failed to save config to {config_file}: {e}")
        raise


def validate_config(config_data: Dict[str, Any]) -> Config:
    """Validate configuration data and return Config object."""
    return Config(**config_data)

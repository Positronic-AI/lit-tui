"""
Settings screen for LIT TUI.

This module provides a basic settings interface for configuration.
"""

import logging
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from ..config import Config


logger = logging.getLogger(__name__)


class SettingsScreen(ModalScreen):
    """Modal settings screen."""
    
    CSS = """
    SettingsScreen {
        align: center middle;
    }
    
    .settings-dialog {
        width: 60;
        height: 22;
        padding: 2;
    }
    
    .settings-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 2;
    }
    
    .settings-info {
        margin: 1 0;
        text-align: center;
    }
    
    .buttons {
        margin-top: 2;
        align: center middle;
    }
    
    #close {
        width: 20;
        margin: 1;
    }
    """
    
    def __init__(self, config: Config, **kwargs):
        """Initialize settings screen."""
        super().__init__(**kwargs)
        self.config = config
        
    def compose(self) -> ComposeResult:
        """Compose the settings screen."""
        with Center():
            with Vertical(classes="settings-dialog"):
                yield Label("⚙️ Settings", classes="settings-title")
                
                yield Static(f"Model: {self.config.ollama.default_model or 'Auto-detect'}", classes="settings-info")
                yield Static(f"Theme: {self.config.ui.theme}", classes="settings-info")
                yield Static(f"Debug: {'Enabled' if self.config.debug else 'Disabled'}", classes="settings-info")
                yield Static(f"MCP: {'Enabled' if self.config.mcp.enabled else 'Disabled'}", classes="settings-info")
                
                yield Static("Configuration file: ~/.lit-tui/config.json", classes="settings-info")
                yield Static("", classes="settings-info")  # Spacer
                yield Static("Press ESC or click Close to exit", classes="settings-info")
                
                with Horizontal(classes="buttons"):
                    yield Button("Close", id="close", variant="primary")
    
    @on(Button.Pressed, "#close")
    async def on_close(self, event: Button.Pressed) -> None:
        """Close the settings screen."""
        self.app.pop_screen()
        
    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key == "escape":
            event.prevent_default()  # Prevent ESC from bubbling up to main app
            event.stop()
            self.app.pop_screen()

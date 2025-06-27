"""
Model selection screen for LIT TUI.

This module provides a model selection interface with a list of available models.
"""

import logging
from typing import List, Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList
from textual.widgets.option_list import Option

from ..config import Config
from ..services.ollama_client import OllamaModel


logger = logging.getLogger(__name__)


class ModelSelectionScreen(ModalScreen[str]):
    """Modal screen for selecting Ollama models."""
    
    CSS = """
    ModelSelectionScreen {
        align: center middle;
    }
    
    .model-dialog {
        width: 70;
        height: 25;
        padding: 2;
    }
    
    .model-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    
    .model-list {
        height: 1fr;
        border: round $primary;
        margin: 1 0;
    }
    
    .buttons {
        margin-top: 1;
        align: center middle;
    }
    
    .dialog-button {
        width: 15;
        margin: 0 1;
    }
    """
    
    def __init__(self, config: Config, ollama_client, current_model: Optional[str] = None, **kwargs):
        """Initialize model selection screen."""
        super().__init__(**kwargs)
        self.config = config
        self.ollama_client = ollama_client
        self.current_model = current_model
        self.models: List[OllamaModel] = []
        self.selected_model: Optional[str] = None
        
    def compose(self) -> ComposeResult:
        """Compose the model selection screen."""
        with Center():
            with Vertical(classes="model-dialog"):
                yield Label("🤖 Select Model", classes="model-title")
                
                if self.current_model:
                    yield Label(f"Current: {self.current_model}", classes="model-title")
                
                yield OptionList(id="model_list", classes="model-list")
                
                yield Label("↑↓ Navigate, Enter to select, ESC to cancel", classes="model-title")
                
                with Horizontal(classes="buttons"):
                    yield Button("Cancel", id="cancel", classes="dialog-button")
                    yield Button("Select", id="select", variant="primary", classes="dialog-button")
    
    async def on_mount(self) -> None:
        """Called when screen is mounted."""
        await self.load_models()
    
    async def load_models(self) -> None:
        """Load available models from Ollama."""
        try:
            self.models = await self.ollama_client.get_models()
            
            model_list = self.query_one("#model_list", OptionList)
            
            # Clear existing options
            model_list.clear_options()
            
            if not self.models:
                # No models available
                model_list.add_option(Option("No models available. Please pull a model with 'ollama pull <model>'", disabled=True))
            else:
                # Add models to list
                for model in self.models:
                    is_current = model.name == self.current_model
                    size_str = self._format_size(model.size)
                    
                    # Create option text
                    current_indicator = " (current)" if is_current else ""
                    prompt = f"📦 {model.name}{current_indicator}"
                    disabled = False
                    
                    # Store the model name as the option id
                    option = Option(prompt, id=model.name, disabled=disabled)
                    model_list.add_option(option)
                    
                    # Select current model by default
                    if is_current:
                        model_list.highlighted = len(model_list._options) - 1
                    
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            # Show error in the list
            model_list = self.query_one("#model_list", OptionList)
            model_list.clear_options()
            model_list.add_option(Option(f"Error loading models: {e}", disabled=True))
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format."""
        if size_bytes == 0:
            return "Unknown size"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} PB"
    
    @on(OptionList.OptionSelected, "#model_list")
    async def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        if event.option.id and not event.option.disabled:
            self.selected_model = str(event.option.id)
            await self.select_model()
    
    @on(Button.Pressed, "#select")
    async def on_select_pressed(self, event: Button.Pressed) -> None:
        """Handle select button press."""
        # Get currently highlighted option
        model_list = self.query_one("#model_list", OptionList)
        if model_list.highlighted is not None:
            option = model_list.get_option_at_index(model_list.highlighted)
            if option and option.id:
                self.selected_model = str(option.id)
                await self.select_model()
        else:
            # No model selected, return special value
            self.dismiss("__no_selection__")
    
    @on(Button.Pressed, "#cancel")
    async def on_cancel_pressed(self, event: Button.Pressed) -> None:
        """Handle cancel button press."""
        self.dismiss()
    
    async def select_model(self) -> None:
        """Select the chosen model."""
        try:
            if self.selected_model and self.selected_model != self.current_model:
                # Exit with the selected model
                self.dismiss(self.selected_model)
            elif self.selected_model == self.current_model:
                # Return special value to indicate "already selected"
                self.dismiss("__already_selected__")
            else:
                # Return special value to indicate "no selection"
                self.dismiss("__no_selection__")
        except Exception as e:
            logger.error(f"Error in select_model: {e}")
            # Return error info
            self.dismiss(f"__error__:{e}")
    
    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key == "escape":
            event.prevent_default()  # Prevent ESC from bubbling up to main app
            event.stop()
            self.dismiss()

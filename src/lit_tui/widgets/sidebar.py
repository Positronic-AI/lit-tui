"""
Sidebar widget for session management and navigation.

This widget provides navigation between chat sessions, model selection,
and quick access to settings.
"""

import logging
from typing import List, Optional

from textual import on, work
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import Button, Label, Static, OptionList
from textual.widgets.option_list import Option

from ..config import Config


logger = logging.getLogger(__name__)


class Sidebar(Widget):
    """Sidebar widget for navigation and session management."""
    
    CSS = """
    Sidebar {
        background: $background;
        color: $text;
        padding: 1;
    }
    
    .sidebar-section {
        margin: 1 0;
        padding: 0;
    }
    
    .title-row {
        height: 1;
        width: 100%;
        layout: horizontal;
        align: left middle;
    }
    
    .sidebar-title {
        color: $text;
        margin: 0;
        padding: 0;
        height: 1;
        width: 1fr;
        text-align: left;
        content-align: left middle;
    }
    
    .inline-button {
        height: 1;
        width: auto;
        margin: 0;
        padding: 0 1;
        min-width: 8;
        max-height: 1;
    }
    
    .model-info {
        background: $background;
        padding: 0;
        margin: 1 0;
    }
    
    .session-list {
        height: 1fr;
    }
    """
    
    def __init__(self, config: Config, **kwargs):
        """Initialize sidebar."""
        super().__init__(**kwargs)
        self.config = config
        self.sessions: List[dict] = []
        
    def compose(self):
        """Compose the sidebar layout."""
        # Model information - compact with inline button
        with Vertical(classes="sidebar-section"):
            with Horizontal(classes="title-row"):
                yield Label("Model", classes="sidebar-title")
                yield Button("Change", classes="inline-button", id="change_model")
            yield Static("📋 Loading...", classes="model-info", id="model_display")
        
        # Session management - compact with inline button
        with Vertical(classes="sidebar-section"):
            with Horizontal(classes="title-row"):
                yield Label("Sessions", classes="sidebar-title") 
                yield Button("New", classes="inline-button", id="new_chat")
            yield OptionList(id="session_list", classes="session-list")
    
    async def on_mount(self) -> None:
        """Called when sidebar is mounted."""
        await self.load_sessions()
        
        # Update model display once the screen is available
        if hasattr(self.screen, 'current_model') and self.screen.current_model:
            self.update_model_display(self.screen.current_model)
    
    @on(Button.Pressed, "#new_chat")
    async def on_new_chat(self, event: Button.Pressed) -> None:
        """Handle new chat button."""
        # Send action to parent screen
        await self.screen.new_chat()
    
    @on(Button.Pressed, "#change_model")
    async def on_change_model(self, event: Button.Pressed) -> None:
        """Handle change model button."""
        # Use a worker to handle the modal
        self.run_worker(self._handle_model_change())
    
    async def _handle_model_change(self) -> None:
        """Handle model change in a worker."""
        from ..screens.model_selection import ModelSelectionScreen
        
        try:
            current_model = getattr(self.screen, 'current_model', None)
            ollama_client = getattr(self.screen, 'ollama_client', None)
            
            if not ollama_client:
                self.app.notify("Ollama client not available", severity="error")
                return
                
            model_screen = ModelSelectionScreen(self.config, ollama_client, current_model)
            
            # Push screen and wait for result
            result = await self.app.push_screen_wait(model_screen)
            
            # If a model was selected, change to it
            if result and hasattr(self.screen, 'change_model'):
                await self.screen.change_model(result)
                
        except Exception as e:
            logger.error(f"Error opening model selection: {e}")
            self.app.notify(f"Error opening model selection: {e}", severity="error")
    
    @on(OptionList.OptionSelected, "#session_list")
    async def on_session_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle session selection."""
        if event.option.id:
            session_id = str(event.option.id)
            # Load selected session
            if hasattr(self.screen, 'storage_service') and hasattr(self.screen, 'load_session'):
                try:
                    await self.screen.load_session(session_id)
                    self.app.notify(f"Loaded session")
                except Exception as e:
                    logger.error(f"Error loading session: {e}")
                    self.app.notify(f"Error loading session: {e}", severity="error")
            else:
                self.app.notify(f"Loading session (not implemented)")
    
    async def load_sessions(self) -> None:
        """Load sessions from storage."""
        try:
            # Get storage service from screen
            if hasattr(self.screen, 'storage_service'):
                storage_service = self.screen.storage_service
                sessions = await storage_service.list_sessions(limit=10)
                
                session_list = self.query_one("#session_list", OptionList)
                
                # Clear existing options
                session_list.clear_options()
                
                # Add sessions to list
                for session_data in sessions:
                    option = Option(
                        f"💬 {session_data['title']}", 
                        id=session_data["session_id"]
                    )
                    session_list.add_option(option)
                    
            else:
                # Fallback to placeholder sessions if no storage service
                session_list = self.query_one("#session_list", OptionList)
                session_list.clear_options()
                
                placeholder_sessions = [
                    {"id": "1", "title": "Previous Chat 1"},
                    {"id": "2", "title": "Previous Chat 2"},
                    {"id": "3", "title": "Previous Chat 3"},
                ]
                
                for session in placeholder_sessions:
                    option = Option(f"💬 {session['title']}", id=session["id"])
                    session_list.add_option(option)
                
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
    
    async def add_session(self, session_id: str, title: str) -> None:
        """Add a new session to the list."""
        try:
            session_list = self.query_one("#session_list", OptionList)
            option = Option(f"💬 {title}", id=session_id)
            session_list.add_option(option)
            
        except Exception as e:
            logger.error(f"Error adding session: {e}")
    
    def update_model_display(self, model_name: str) -> None:
        """Update the displayed model name."""
        try:
            model_display = self.query_one("#model_display", Static)
            model_display.update(f"📋 {model_name}")
            
        except Exception as e:
            logger.error(f"Error updating model display: {e}")

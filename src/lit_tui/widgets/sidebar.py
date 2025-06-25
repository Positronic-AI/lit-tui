"""
Sidebar widget for session management and navigation.

This widget provides navigation between chat sessions, model selection,
and quick access to settings.
"""

import logging
from typing import List, Optional

from textual import on
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Button, Label, ListItem, ListView, Static

from ..config import Config


logger = logging.getLogger(__name__)


class SessionItem(ListItem):
    """Individual session item in the sidebar."""
    
    def __init__(self, session_id: str, title: str, **kwargs):
        """Initialize session item."""
        super().__init__(**kwargs)
        self.session_id = session_id
        self.title = title


class Sidebar(Widget):
    """Sidebar widget for navigation and session management."""
    
    CSS = """
    Sidebar {
        background: $surface;
        color: $text;
        padding: 1;
    }
    
    .sidebar-section {
        margin: 1 0;
        border: round $primary;
        padding: 1;
    }
    
    .sidebar-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    
    .model-info {
        background: $primary 20%;
        padding: 1;
        border: round $primary;
        margin: 1 0;
    }
    
    .session-list {
        height: 1fr;
        border: round $primary;
    }
    
    .sidebar-button {
        width: 100%;
        margin: 1 0;
    }
    """
    
    def __init__(self, config: Config, **kwargs):
        """Initialize sidebar."""
        super().__init__(**kwargs)
        self.config = config
        self.sessions: List[dict] = []
        
    def compose(self):
        """Compose the sidebar layout."""
        yield Label("LIT TUI", classes="sidebar-title")
        
        # Model information
        with Vertical(classes="sidebar-section"):
            yield Label("Model", classes="sidebar-title")
            model_name = self.config.ollama.default_model or "llama2"
            yield Static(f"📋 {model_name}", classes="model-info")
            yield Button("Change Model", classes="sidebar-button", id="change_model")
        
        # Session management
        with Vertical(classes="sidebar-section"):
            yield Label("Sessions", classes="sidebar-title")
            yield Button("New Chat", classes="sidebar-button", id="new_chat")
            yield Button("Save Session", classes="sidebar-button", id="save_session")
            yield ListView(id="session_list", classes="session-list")
        
        # Settings and tools
        with Vertical(classes="sidebar-section"):
            yield Label("Tools", classes="sidebar-title")
            yield Button("Settings", classes="sidebar-button", id="settings")
            yield Button("MCP Tools", classes="sidebar-button", id="mcp_tools")
            yield Button("About", classes="sidebar-button", id="about")
    
    async def on_mount(self) -> None:
        """Called when sidebar is mounted."""
        await self.load_sessions()
    
    @on(Button.Pressed, "#new_chat")
    async def on_new_chat(self, event: Button.Pressed) -> None:
        """Handle new chat button."""
        # Send action to parent screen
        await self.screen.new_chat()
    
    @on(Button.Pressed, "#save_session") 
    async def on_save_session(self, event: Button.Pressed) -> None:
        """Handle save session button."""
        await self.screen.save_session()
    
    @on(Button.Pressed, "#change_model")
    async def on_change_model(self, event: Button.Pressed) -> None:
        """Handle change model button."""
        # TODO: Implement model selection
        self.app.notify("Model selection coming soon!")
    
    @on(Button.Pressed, "#settings")
    async def on_settings(self, event: Button.Pressed) -> None:
        """Handle settings button."""
        # TODO: Implement settings screen
        self.app.notify("Settings screen coming soon!")
    
    @on(Button.Pressed, "#mcp_tools")
    async def on_mcp_tools(self, event: Button.Pressed) -> None:
        """Handle MCP tools button."""
        # Show MCP status and available tools
        if hasattr(self.screen, 'mcp_client'):
            try:
                health = await self.screen.mcp_client.health_check()
                tools = self.screen.mcp_client.get_available_tools()
                
                if health["enabled"] and tools:
                    tool_names = [f"• {tool.name} - {tool.description}" for tool in tools[:5]]
                    if len(tools) > 5:
                        tool_names.append(f"... and {len(tools) - 5} more")
                    
                    status_msg = f"MCP Tools Available:\n" + "\n".join(tool_names)
                    self.app.notify(status_msg)
                else:
                    self.app.notify("No MCP tools available. Check configuration.", severity="warning")
            except Exception as e:
                self.app.notify(f"MCP error: {e}", severity="error")
        else:
            self.app.notify("MCP tools management coming soon!")
    
    @on(Button.Pressed, "#about")
    async def on_about(self, event: Button.Pressed) -> None:
        """Handle about button."""
        # TODO: Implement about dialog
        self.app.notify("LIT TUI v0.1.0 - Made with ❤️ by LIT")
    
    @on(ListView.Selected, "#session_list")
    async def on_session_selected(self, event: ListView.Selected) -> None:
        """Handle session selection."""
        if isinstance(event.item, SessionItem):
            # Load selected session
            if hasattr(self.screen, 'storage_service') and hasattr(self.screen, 'load_session'):
                try:
                    await self.screen.load_session(event.item.session_id)
                    self.app.notify(f"Loaded session: {event.item.title}")
                except Exception as e:
                    logger.error(f"Error loading session: {e}")
                    self.app.notify(f"Error loading session: {e}", severity="error")
            else:
                self.app.notify(f"Loading session: {event.item.title} (not implemented)")
    
    async def load_sessions(self) -> None:
        """Load sessions from storage."""
        try:
            # Get storage service from screen
            if hasattr(self.screen, 'storage_service'):
                storage_service = self.screen.storage_service
                sessions = await storage_service.list_sessions(limit=10)
                
                session_list = self.query_one("#session_list", ListView)
                
                # Clear existing items
                session_list.clear()
                
                # Add sessions to list
                for session_data in sessions:
                    item = SessionItem(session_data["session_id"], session_data["title"])
                    item.update(f"💬 {session_data['title']}")
                    await session_list.append(item)
                    
            else:
                # Fallback to placeholder sessions if no storage service
                session_list = self.query_one("#session_list", ListView)
                
                placeholder_sessions = [
                    {"id": "1", "title": "Previous Chat 1"},
                    {"id": "2", "title": "Previous Chat 2"},
                    {"id": "3", "title": "Previous Chat 3"},
                ]
                
                for session in placeholder_sessions:
                    item = SessionItem(session["id"], session["title"])
                    item.update(f"💬 {session['title']}")
                    await session_list.append(item)
                
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
    
    async def add_session(self, session_id: str, title: str) -> None:
        """Add a new session to the list."""
        try:
            session_list = self.query_one("#session_list", ListView)
            item = SessionItem(session_id, title)
            item.update(f"💬 {title}")
            await session_list.append(item)
            
        except Exception as e:
            logger.error(f"Error adding session: {e}")
    
    def update_model_display(self, model_name: str) -> None:
        """Update the displayed model name."""
        try:
            model_info = self.query_one(".model-info", Static)
            model_info.update(f"📋 {model_name}")
            
        except Exception as e:
            logger.error(f"Error updating model display: {e}")

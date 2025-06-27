"""
Sidebar widget for session management and navigation.

This widget provides navigation between chat sessions, model selection,
and quick access to settings.
"""

import logging
from datetime import datetime
from typing import List, Optional

from textual import on, work
from textual.containers import Vertical, Horizontal
from textual.widget import Widget
from textual.widgets import Button, Label, Static, OptionList
from textual.widgets.option_list import Option
from textual.events import Click

from ..config import Config


logger = logging.getLogger(__name__)


class TerminalButton(Button):
    """Button that uses terminal colors."""
    
    DEFAULT_CSS = """
    TerminalButton {
        border: none;
        height: auto;
        min-height: 1;
    }
    
    TerminalButton:hover {
        border: none;
        text-style: underline;
    }
    
    TerminalButton:focus {
        border: none;
        text-style: underline;
    }
    """


class TerminalOptionList(OptionList):
    """OptionList that uses terminal colors."""
    
    DEFAULT_CSS = """
    TerminalOptionList {
        border: none;
    }
    
    TerminalOptionList > .option-list--option {
    }
    
    TerminalOptionList > .option-list--option-hover {
        text-style: underline;
    }
    
    TerminalOptionList > .option-list--option-highlighted {
        text-style: bold;
    }
    
    TerminalOptionList > .option-list--option-selected {
        text-style: bold underline;
    }
    """
    
    def on_mount(self) -> None:
        """Override mount to remove background styling."""
        super().on_mount()
        # Try to force remove background styling
        try:
            # Clear the widget's own styling
            self.styles.background = None
            # Also try to remove any computed styles
            if hasattr(self, '_styles'):
                if hasattr(self._styles, 'background'):
                    self._styles.background = None
        except Exception as e:
            logger.debug(f"Could not remove OptionList background: {e}")


class Sidebar(Widget):
    """Sidebar widget for navigation and session management."""
    
    CSS = """
    Sidebar {
        padding: 1;
    }
    
    .sidebar-section {
        margin: 0;
        padding: 0;
    }
    
    /* Model section - auto height to accommodate long model names */
    .model-section {
        height: auto;
        min-height: 2;
        margin-bottom: 1;
    }
    
    .model-button {
        width: 100%;
        height: auto;
        min-height: 1;
        margin: 0;
        padding: 0;
        text-align: left;
        content-align: left middle;
        border: none;
    }
    
    .model-button:hover {
        border: none;
        text-style: underline;
    }
    
    .model-button:focus {
        border: none;
        text-style: underline;
    }
    
    /* Sessions section - takes most space */
    .sessions-section {
        height: 1fr;
        margin-bottom: 1;
    }
    
    /* Notifications section - space for multiple notifications */
    .notifications-section {
        height: auto;
        max-height: 8;
        min-height: 2;
    }
    
    .title-row {
        height: 1;
        width: 100%;
        layout: horizontal;
        align: left middle;
    }
    
    .sidebar-title {
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
    
    .inline-button:disabled {
        opacity: 50%;
        text-style: dim;
    }
    
    .session-list {
        height: 1fr;
    }
    
    .notification-display {
        height: auto;
        margin: 0;
        padding: 0;
        content-align: left top;
    }
    
    .notification-container {
        height: auto;
        max-height: 8;
        overflow-y: auto;
        padding: 0;
        margin: 0;
    }
    
    .notification-item {
        width: 100%;
        height: auto;
        margin: 0;
        padding: 0;
        text-align: left;
        content-align: left top;
        background: transparent;
    }
    
    .notification-item:hover {
        background: $surface;
        text-style: dim;
    }
    """
    
    def __init__(self, config: Config, **kwargs):
        """Initialize sidebar."""
        super().__init__(**kwargs)
        self.config = config
        self.sessions: List[dict] = []
        self.notifications: List[dict] = []  # Stack of notifications (no limit now)
        self.notification_id_counter = 0  # For unique notification IDs
        
    def compose(self):
        """Compose the sidebar layout."""
        # Model information - just a title and model button (very compact, 2 lines)
        with Vertical(classes="sidebar-section model-section"):
            yield Label("Model", classes="sidebar-title")
            yield TerminalButton("📋 Loading...", classes="model-button", id="change_model")
        
        # Session management - takes up most of the space
        with Vertical(classes="sidebar-section sessions-section"):
            with Horizontal(classes="title-row"):
                yield Label("Sessions", classes="sidebar-title") 
                yield Button("Del", classes="inline-button", id="delete_session")
                yield Button("New", classes="inline-button", id="new_chat")
            yield TerminalOptionList(id="session_list", classes="session-list")
            
        # Notifications area - compact at bottom, scrollable
        with Vertical(classes="sidebar-section notifications-section"):
            with Vertical(id="notification_container", classes="notification-container"):
                pass  # Notifications will be added dynamically
    
    async def on_mount(self) -> None:
        """Called when sidebar is mounted."""
        await self.load_sessions()
        
        # Update model display once the screen is available
        if hasattr(self.screen, 'current_model') and self.screen.current_model:
            self.update_model_display(self.screen.current_model)
        
        # Initially disable delete button since no session is loaded yet
        self.update_delete_button_state(session_is_saved=False)
    
    @on(Button.Pressed, "#new_chat")
    async def on_new_chat(self, event: Button.Pressed) -> None:
        """Handle new chat button."""
        # Send action to parent screen
        await self.screen.new_chat()
    
    @on(Button.Pressed, "#delete_session")
    async def on_delete_session(self, event: Button.Pressed) -> None:
        """Handle delete session button - deletes the current session."""
        try:
            # Check if we have a current session to delete
            if not hasattr(self.screen, 'current_session') or not self.screen.current_session:
                self.show_notification("No current session to delete", "warning")
                return
            
            current_session = self.screen.current_session
            
            # Only allow deletion of saved sessions
            if not current_session.is_saved:
                self.show_notification("Cannot delete unsaved session", "warning")
                return
            
            session_id = current_session.session_id
            
            # Delete the current session through the storage service
            if hasattr(self.screen, 'storage_service'):
                storage_service = self.screen.storage_service
                success = await storage_service.delete_session(session_id)
                
                if success:
                    # Remove from the session list if it's displayed there
                    session_list = self.query_one("#session_list", TerminalOptionList)
                    # Find and remove the session from the list
                    for i, option in enumerate(session_list._options):
                        if option.id == session_id:
                            session_list.remove_option_at_index(i)
                            break
                    
                    # Start a new chat session
                    await self.screen.new_chat()
                    
                    self.show_notification("Current session deleted", "success")
                else:
                    self.show_notification("Failed to delete session", "error")
            else:
                self.show_notification("Storage service not available", "error")
                
        except Exception as e:
            logger.error(f"Error deleting current session: {e}")
            self.show_notification(f"Error deleting session: {e}", "error")
    
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
                self.show_notification("Ollama client not available", "error")
                return
                
            model_screen = ModelSelectionScreen(self.config, ollama_client, current_model)
            
            # Push screen and wait for result
            result = await self.app.push_screen_wait(model_screen)
            
            # If a model was selected, change to it
            if result:
                if result == "__already_selected__":
                    self.show_notification("Model is already selected", "info")
                elif result == "__no_selection__":
                    self.show_notification("No model selected", "warning")
                elif result.startswith("__error__:"):
                    error_msg = result.split(":", 1)[1]
                    self.show_notification(f"Error changing model: {error_msg}", "error")
                elif hasattr(self.screen, 'change_model'):
                    await self.screen.change_model(result)
                
        except Exception as e:
            logger.error(f"Error opening model selection: {e}")
            self.show_notification(f"Error opening model selection: {e}", "error")
    
    @on(TerminalOptionList.OptionSelected, "#session_list")
    async def on_session_selected(self, event: TerminalOptionList.OptionSelected) -> None:
        """Handle session selection."""
        if event.option.id:
            session_id = str(event.option.id)
            # Load selected session
            if hasattr(self.screen, 'storage_service') and hasattr(self.screen, 'load_session'):
                try:
                    await self.screen.load_session(session_id)
                    self.show_notification("Loaded session", "success")
                except Exception as e:
                    logger.error(f"Error loading session: {e}")
                    self.show_notification(f"Error loading session: {e}", "error")
            else:
                self.show_notification("Loading session (not implemented)", "warning")
    
    async def load_sessions(self) -> None:
        """Load sessions from storage."""
        try:
            # Get storage service from screen
            if hasattr(self.screen, 'storage_service'):
                storage_service = self.screen.storage_service
                sessions = await storage_service.list_sessions(limit=10)
                
                session_list = self.query_one("#session_list", TerminalOptionList)
                
                # Clear existing options
                session_list.clear_options()
                
                # Add sessions to list
                for session_data in sessions:
                    option = Option(
                        session_data['title'], 
                        id=session_data["session_id"]
                    )
                    session_list.add_option(option)
                    
            else:
                # Fallback to placeholder sessions if no storage service
                session_list = self.query_one("#session_list", TerminalOptionList)
                session_list.clear_options()
                
                placeholder_sessions = [
                    {"id": "1", "title": "Previous Chat 1"},
                    {"id": "2", "title": "Previous Chat 2"},
                    {"id": "3", "title": "Previous Chat 3"},
                ]
                
                for session in placeholder_sessions:
                    option = Option(session['title'], id=session["id"])
                    session_list.add_option(option)
                
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
    
    async def add_session(self, session_id: str, title: str) -> None:
        """Add a new session to the list."""
        try:
            session_list = self.query_one("#session_list", TerminalOptionList)
            option = Option(title, id=session_id)
            session_list.add_option(option)
            
        except Exception as e:
            logger.error(f"Error adding session: {e}")
    
    def update_model_display(self, model_name: str) -> None:
        """Update the displayed model name."""
        try:
            model_button = self.query_one("#change_model", TerminalButton)
            model_button.label = f"📋 {model_name}"
            
        except Exception as e:
            logger.error(f"Error updating model display: {e}")
    
    def update_delete_button_state(self, session_is_saved: bool) -> None:
        """Update the delete button state based on current session status."""
        try:
            delete_button = self.query_one("#delete_session", Button)
            
            if session_is_saved:
                # Session is saved, enable delete button
                delete_button.disabled = False
                delete_button.tooltip = "Delete current session"
            else:
                # Session not saved yet, disable delete button to prevent accidents
                delete_button.disabled = True
                delete_button.tooltip = "Delete disabled - current session not saved yet"
                
        except Exception as e:
            logger.error(f"Error updating delete button state: {e}")
            
    def show_notification(self, message: str, severity: str = "info") -> None:
        """Show a notification in the sidebar."""
        try:
            # Add emoji based on severity
            emoji = {
                "info": "ℹ️",
                "success": "✅", 
                "warning": "⚠️",
                "error": "❌"
            }.get(severity, "ℹ️")
            
            # Create unique notification
            self.notification_id_counter += 1
            notification_id = f"notification_{self.notification_id_counter}"
            
            notification = {
                "id": notification_id,
                "message": f"{emoji} {message}",
                "timestamp": datetime.now(),
                "severity": severity
            }
            self.notifications.append(notification)
            
            # Add notification to UI
            self._add_notification_to_ui(notification)
            
            # Auto-scroll to newest notification
            self._scroll_to_newest()
            
        except Exception as e:
            logger.error(f"Error showing notification: {e}")
    
    def _add_notification_to_ui(self, notification: dict) -> None:
        """Add a single notification to the UI."""
        try:
            container = self.query_one("#notification_container", Vertical)
            
            # Create clickable notification
            notification_widget = Static(
                notification["message"], 
                id=notification["id"],
                classes="notification-item"
            )
            
            # Store notification data as a custom attribute
            notification_widget._notification_data = notification
            
            container.mount(notification_widget)
            
        except Exception as e:
            logger.error(f"Error adding notification to UI: {e}")
    
    def _scroll_to_newest(self) -> None:
        """Auto-scroll to show the newest notification."""
        try:
            container = self.query_one("#notification_container", Vertical)
            # Scroll to bottom to show newest notification
            container.scroll_end(animate=False)
        except Exception as e:
            logger.error(f"Error scrolling to newest notification: {e}")
    
    def on_click(self, event: Click) -> None:
        """Handle clicks on notification items."""
        # Check if the click was on a notification item
        if hasattr(event.widget, 'has_class') and event.widget.has_class("notification-item"):
            self._dismiss_notification(event.widget)
    
    def _dismiss_notification(self, notification_widget: Static) -> None:
        """Dismiss a specific notification."""
        try:
            notification_data = getattr(notification_widget, '_notification_data', None)
            
            if notification_data:
                # Remove from notifications list
                self.notifications = [n for n in self.notifications if n["id"] != notification_data["id"]]
                
                # Remove from UI
                notification_widget.remove()
                
                logger.debug(f"Dismissed notification: {notification_data['id']}")
            
        except Exception as e:
            logger.error(f"Error dismissing notification: {e}")

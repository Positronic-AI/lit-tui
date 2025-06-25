"""
Main chat screen for LIT TUI.

This module contains the primary chat interface including message display,
input handling, and session management.
"""

import asyncio
import logging
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from ..config import Config
from ..widgets import MessageList, Sidebar


logger = logging.getLogger(__name__)


class ChatScreen(Screen):
    """Main chat screen."""
    
    CSS = """
    ChatScreen {
        layout: horizontal;
    }
    
    .sidebar {
        width: 25%;
        background: $surface;
        border-right: thick $primary;
    }
    
    .main-area {
        width: 75%;
        layout: vertical;
    }
    
    .chat-area {
        height: 1fr;
        background: $background;
    }
    
    .input-area {
        height: auto;
        background: $surface;
        border-top: thick $primary;
        padding: 1;
    }
    
    .input-container {
        layout: horizontal;
        height: auto;
    }
    
    .chat-input {
        width: 1fr;
        margin-right: 1;
    }
    
    .send-button {
        width: auto;
    }
    
    .status-bar {
        height: 1;
        background: $primary;
        color: $text;
        text-align: center;
    }
    """
    
    def __init__(self, config: Config, **kwargs):
        """Initialize chat screen."""
        super().__init__(**kwargs)
        self.config = config
        self.current_session_id: Optional[str] = None
        self.is_generating = False
        
    def compose(self) -> ComposeResult:
        """Compose the chat screen layout."""
        with Horizontal():
            # Sidebar for session management
            with Vertical(classes="sidebar"):
                yield Sidebar(self.config)
                
            # Main chat area
            with Vertical(classes="main-area"):
                # Chat messages area
                with Vertical(classes="chat-area"):
                    yield MessageList(id="messages")
                    
                # Input area
                with Vertical(classes="input-area"):
                    yield Static("Ready", id="status", classes="status-bar")
                    with Horizontal(classes="input-container"):
                        yield Input(
                            placeholder="Type your message here... (Enter to send, Shift+Enter for new line)",
                            id="chat_input",
                            classes="chat-input"
                        )
                        yield Button("Send", id="send_button", classes="send-button")
    
    async def on_mount(self) -> None:
        """Called when screen is mounted."""
        # Focus the input field
        self.query_one("#chat_input", Input).focus()
        
        # Initialize with a new session
        await self.new_chat()
        
    @on(Input.Submitted, "#chat_input")
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle message input submission."""
        if not self.is_generating and event.value.strip():
            await self.send_message(event.value.strip())
            event.input.value = ""
            
    @on(Button.Pressed, "#send_button")
    async def on_send_button_pressed(self, event: Button.Pressed) -> None:
        """Handle send button press."""
        chat_input = self.query_one("#chat_input", Input)
        if not self.is_generating and chat_input.value.strip():
            await self.send_message(chat_input.value.strip())
            chat_input.value = ""
            chat_input.focus()
    
    async def send_message(self, message: str) -> None:
        """Send a message and get response."""
        if self.is_generating:
            return
            
        try:
            self.is_generating = True
            self.update_status("Sending message...")
            
            # Add user message to chat
            message_list = self.query_one("#messages", MessageList)
            await message_list.add_message("user", message)
            
            # Start generating response
            self.update_status("Generating response...")
            await self.generate_response(message)
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.notify(f"Error: {e}", severity="error")
        finally:
            self.is_generating = False
            self.update_status("Ready")
    
    @work(exclusive=True)
    async def generate_response(self, message: str) -> None:
        """Generate response from Ollama (placeholder implementation)."""
        try:
            # TODO: Implement actual Ollama integration
            # For now, just simulate a response
            await asyncio.sleep(1)  # Simulate processing time
            
            # Add assistant response
            message_list = self.query_one("#messages", MessageList)
            response = f"Echo: {message}"  # Placeholder response
            await message_list.add_message("assistant", response)
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            message_list = self.query_one("#messages", MessageList)
            await message_list.add_message("assistant", f"Error: {e}")
    
    def update_status(self, message: str) -> None:
        """Update status bar."""
        status = self.query_one("#status", Static)
        status.update(message)
    
    async def new_chat(self) -> None:
        """Start a new chat session."""
        # TODO: Implement session management
        self.current_session_id = f"session_{asyncio.get_event_loop().time()}"
        
        # Clear messages
        message_list = self.query_one("#messages", MessageList)
        await message_list.clear()
        
        # Add welcome message
        await message_list.add_message(
            "assistant", 
            "Hello! I'm your AI assistant. How can I help you today?"
        )
        
        self.update_status(f"New session: {self.current_session_id}")
        self.notify("Started new chat session")
    
    async def save_session(self) -> None:
        """Save current session."""
        # TODO: Implement session saving
        self.notify("Session saved (not implemented yet)")
    
    async def open_session(self) -> None:
        """Open existing session."""
        # TODO: Implement session loading
        self.notify("Open session (not implemented yet)")

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
from ..services import OllamaClient, StorageService
from ..services.storage import ChatMessage
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
        self.ollama_client = OllamaClient(config)
        self.storage_service = StorageService(config)
        self.current_session = None
        self.current_model: Optional[str] = None
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
                    yield Static("Initializing...", id="status", classes="status-bar")
                    with Horizontal(classes="input-container"):
                        yield Input(
                            placeholder="Type your message here... (Enter to send, Shift+Enter for new line)",
                            id="chat_input",
                            classes="chat-input"
                        )
                        yield Button("Send", id="send_button", classes="send-button")
    
    async def on_mount(self) -> None:
        """Called when screen is mounted."""
        # Initialize services
        await self._initialize_services()
        
        # Focus the input field
        self.query_one("#chat_input", Input).focus()
        
        # Start with a new session
        await self.new_chat()
        
    async def _initialize_services(self) -> None:
        """Initialize Ollama and check availability."""
        self.update_status("Checking Ollama connection...")
        
        try:
            is_available = await self.ollama_client.is_available()
            if not is_available:
                self.update_status("⚠️  Ollama not available - check if server is running")
                self.notify("Ollama server not available. Please start Ollama.", severity="warning")
                return
            
            # Get default model
            self.current_model = await self.ollama_client.get_default_model()
            if not self.current_model:
                self.update_status("⚠️  No models found - please pull a model in Ollama")
                self.notify("No Ollama models found. Please pull a model first.", severity="warning")
                return
            
            self.update_status(f"✅ Connected to Ollama - using {self.current_model}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Ollama: {e}")
            self.update_status(f"❌ Ollama error: {e}")
            self.notify(f"Ollama initialization failed: {e}", severity="error")
    
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
            
            # Add to session
            if self.current_session:
                user_msg = ChatMessage(role="user", content=message, model=self.current_model)
                self.current_session.add_message(user_msg)
                await self.storage_service.save_session(self.current_session)
            
            # Start generating response
            self.update_status("🤖 Generating response...")
            await self.generate_response(message)
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.notify(f"Error: {e}", severity="error")
        finally:
            self.is_generating = False
            self.update_status("Ready")
    
    @work(exclusive=True)
    async def generate_response(self, message: str) -> None:
        """Generate response from Ollama with streaming."""
        try:
            if not self.current_model:
                await self._handle_no_model()
                return
            
            # Prepare messages for Ollama
            messages = []
            if self.current_session:
                # Convert session messages to Ollama format
                for msg in self.current_session.messages:
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            # Add system prompt if this is the first message
            if len(messages) == 1:  # Only user message
                system_msg = {
                    "role": "system",
                    "content": "You are a helpful AI assistant. Provide clear, concise, and accurate responses."
                }
                messages.insert(0, system_msg)
            
            # Start streaming response
            message_list = self.query_one("#messages", MessageList)
            response_content = ""
            
            # Add initial assistant message
            await message_list.add_message("assistant", "")
            
            # Stream the response
            async for chunk in self.ollama_client.chat_completion(
                model=self.current_model,
                messages=messages,
                stream=True
            ):
                response_content += chunk
                # Update the last message with accumulated content
                await message_list.update_last_message(response_content)
            
            # Save complete response to session
            if self.current_session and response_content:
                assistant_msg = ChatMessage(
                    role="assistant", 
                    content=response_content,
                    model=self.current_model
                )
                self.current_session.add_message(assistant_msg)
                await self.storage_service.save_session(self.current_session)
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            message_list = self.query_one("#messages", MessageList)
            await message_list.add_message("assistant", f"Error: {e}")
    
    async def _handle_no_model(self) -> None:
        """Handle case where no model is available."""
        message_list = self.query_one("#messages", MessageList)
        error_msg = ("No Ollama model available. Please:\n"
                    "1. Make sure Ollama is running\n"
                    "2. Pull a model (e.g., `ollama pull llama2`)\n"
                    "3. Restart lit-tui")
        await message_list.add_message("assistant", error_msg)
    
    def update_status(self, message: str) -> None:
        """Update status bar."""
        status = self.query_one("#status", Static)
        status.update(message)
    
    async def new_chat(self) -> None:
        """Start a new chat session."""
        try:
            # Create new session
            self.current_session = await self.storage_service.create_session(
                model=self.current_model
            )
            
            # Clear messages
            message_list = self.query_one("#messages", MessageList)
            await message_list.clear()
            
            # Add welcome message
            welcome_msg = "Hello! I'm your AI assistant. How can I help you today?"
            await message_list.add_message("assistant", welcome_msg)
            
            # Add welcome message to session
            if self.current_session:
                assistant_msg = ChatMessage(
                    role="assistant", 
                    content=welcome_msg,
                    model=self.current_model
                )
                self.current_session.add_message(assistant_msg)
                await self.storage_service.save_session(self.current_session)
            
            self.update_status(f"New session: {self.current_session.session_id[:8]}...")
            self.notify("Started new chat session")
            
        except Exception as e:
            logger.error(f"Error creating new session: {e}")
            self.notify(f"Error creating session: {e}", severity="error")
    
    async def save_session(self) -> None:
        """Save current session."""
        try:
            if self.current_session:
                await self.storage_service.save_session(self.current_session)
                self.notify(f"Session saved: {self.current_session.title}")
            else:
                self.notify("No session to save", severity="warning")
        except Exception as e:
            logger.error(f"Error saving session: {e}")
            self.notify(f"Error saving session: {e}", severity="error")
    
    async def open_session(self) -> None:
        """Open existing session."""
        # TODO: Implement session selection dialog
        self.notify("Session selection coming soon!")
    
    async def change_model(self, model_name: str) -> None:
        """Change the current model."""
        try:
            # Verify model is available
            models = await self.ollama_client.get_models()
            if not any(m.name == model_name for m in models):
                self.notify(f"Model {model_name} not found", severity="error")
                return
            
            self.current_model = model_name
            self.update_status(f"✅ Using model: {model_name}")
            self.notify(f"Switched to model: {model_name}")
            
            # Update session model
            if self.current_session:
                self.current_session.model = model_name
                await self.storage_service.save_session(self.current_session)
                
        except Exception as e:
            logger.error(f"Error changing model: {e}")
            self.notify(f"Error changing model: {e}", severity="error")

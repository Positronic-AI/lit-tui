"""
Enhanced input field widget for chat messages.

This widget provides multiline text input with proper key handling
for chat message composition.
"""

import logging
from typing import Optional, Callable

from textual import on
from textual.events import Key
from textual.widget import Widget
from textual.widgets import TextArea


logger = logging.getLogger(__name__)


class ChatInputField(Widget):
    """Enhanced input field for chat messages."""
    
    CSS = """
    ChatInputField {
        height: auto;
        min-height: 3;
        max-height: 10;
        border: round $primary;
        background: $surface;
    }
    
    .chat-textarea {
        border: none;
        background: transparent;
        scrollbar-background: $surface;
        scrollbar-color: $primary;
    }
    """
    
    def __init__(self, placeholder: str = "Type your message...", **kwargs):
        """Initialize the input field."""
        super().__init__(**kwargs)
        self.placeholder = placeholder
        self.on_submit: Optional[Callable[[str], None]] = None
        
    def compose(self):
        """Compose the input field."""
        yield TextArea(
            id="textarea",
            classes="chat-textarea",
            text="",
            show_line_numbers=False,
            tab_behavior="indent"
        )
    
    def set_submit_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback for message submission."""
        self.on_submit = callback
    
    @on(Key)
    async def on_key(self, event: Key) -> None:
        """Handle key events."""
        textarea = self.query_one("#textarea", TextArea)
        
        if event.key == "enter":
            # Check for Shift+Enter (new line) vs Enter (submit)
            if event.shift:
                # Let the default handler add a new line
                return
            else:
                # Submit the message
                event.prevent_default()
                await self._submit_message()
        
    async def _submit_message(self) -> None:
        """Submit the current message."""
        textarea = self.query_one("#textarea", TextArea)
        content = textarea.text.strip()
        
        if content and self.on_submit:
            # Clear the text area
            textarea.text = ""
            
            # Call the submit callback
            await self.on_submit(content)
    
    def focus(self) -> None:
        """Focus the input field."""
        textarea = self.query_one("#textarea", TextArea)
        textarea.focus()
    
    @property
    def text(self) -> str:
        """Get the current text."""
        textarea = self.query_one("#textarea", TextArea)
        return textarea.text
        
    @text.setter
    def text(self, value: str) -> None:
        """Set the text."""
        textarea = self.query_one("#textarea", TextArea)
        textarea.text = value
    
    def clear(self) -> None:
        """Clear the input field."""
        textarea = self.query_one("#textarea", TextArea)
        textarea.text = ""

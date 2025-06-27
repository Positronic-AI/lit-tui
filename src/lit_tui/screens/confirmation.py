"""
Confirmation dialog screen for LIT TUI.

This module provides a simple confirmation dialog for user actions.
"""

from textual.app import ComposeResult
from textual.containers import Center, Middle, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label
from textual import on


class ConfirmationScreen(ModalScreen[bool]):
    """A modal confirmation dialog."""
    
    CSS = """
    ConfirmationScreen {
        align: center middle;
    }
    
    .confirmation-dialog {
        width: 50;
        height: 9;
        border: thick $background 80%;
        background: $surface;
        padding: 1;
    }
    
    .confirmation-message {
        width: 100%;
        height: 3;
        content-align: center middle;
        text-align: center;
    }
    
    .confirmation-buttons {
        width: 100%;
        height: 3;
        layout: horizontal;
        align: center middle;
    }
    
    .confirmation-button {
        margin: 0 1;
        min-width: 8;
    }
    """
    
    def __init__(self, message: str = "Are you sure?", **kwargs):
        """Initialize the confirmation dialog."""
        super().__init__(**kwargs)
        self.message = message
    
    async def on_mount(self) -> None:
        """Called when the screen is mounted."""
        # Focus the "Yes" button by default since user already expressed intent to quit
        try:
            yes_button = self.query_one("#confirm_yes")
            yes_button.focus()
        except Exception:
            pass  # If we can't focus, that's ok
    
    def compose(self) -> ComposeResult:
        """Compose the confirmation dialog."""
        with Center():
            with Middle():
                with Vertical(classes="confirmation-dialog"):
                    yield Label(self.message, classes="confirmation-message")
                    with Horizontal(classes="confirmation-buttons"):
                        yes_button = Button("Yes", variant="primary", id="confirm_yes", classes="confirmation-button")
                        no_button = Button("No", variant="default", id="confirm_no", classes="confirmation-button")
                        yield yes_button
                        yield no_button 
    
    @on(Button.Pressed, "#confirm_yes")
    def on_confirm_yes(self, event: Button.Pressed) -> None:
        """Handle yes button."""
        import logging
        logging.info("YES button pressed - dismissing with True")
        self.dismiss(True)
    
    @on(Button.Pressed, "#confirm_no") 
    def on_confirm_no(self, event: Button.Pressed) -> None:
        """Handle no button."""
        import logging
        logging.info("NO button pressed - dismissing with False")
        self.dismiss(False)
    
    def on_key(self, event) -> None:
        """Handle key presses."""
        import logging
        logging.info(f"Key pressed in confirmation: {event.key}")
        if event.key == "y" or event.key == "Y":
            logging.info("Y key - dismissing with True")
            event.prevent_default()
            self.dismiss(True)
        elif event.key == "n" or event.key == "N":
            logging.info("N key - dismissing with False")
            event.prevent_default()
            self.dismiss(False)
        elif event.key == "escape":
            logging.info("ESC key - dismissing with False")
            event.prevent_default()  # Prevent ESC from bubbling up to main app
            event.stop()
            self.dismiss(False)
        # Remove the Enter key handling - let it follow button focus naturally

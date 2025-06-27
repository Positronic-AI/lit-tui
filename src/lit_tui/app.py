"""
Main application entry point for LIT TUI.

This module contains the main Textual application class and the command-line entry point.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual import work
from textual.widgets import Footer

from .config import Config, load_config
from .screens.chat import ChatScreen


class LitTuiApp(App):
    """Main LIT TUI application."""
    
    CSS_PATH = "app.css"
    TITLE = "LIT TUI"
    SUB_TITLE = "Lightweight Terminal Chat Interface"
    
    BINDINGS = [
        Binding("escape", "quit_with_confirmation", "Quit"),
        Binding("ctrl+q", "quit", "Force Quit", show=False),  # Hidden from footer
        Binding("ctrl+n", "new_chat", "New Chat"),
        Binding("ctrl+o", "open_session", "Open"),
        Binding("ctrl+slash", "help", "Help"),
        Binding("f1", "help", "Help"),
    ]
    
    def __init__(self, config_path: Optional[Path] = None, **kwargs):
        """Initialize the application."""
        # Enable ANSI colors to respect terminal color scheme
        kwargs['ansi_color'] = True
        super().__init__(**kwargs)
        self.config_path = config_path or Path.home() / ".lit-tui"
        self.config: Optional[Config] = None
        
    async def on_mount(self) -> None:
        """Called when the app is mounted."""
        # Load configuration
        self.config = await load_config(self.config_path)
        
        # Set up logging
        log_level = logging.DEBUG if self.config.debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(self.config_path / "lit-tui.log", mode='w'),  # 'w' mode overwrites on each run
                logging.StreamHandler() if self.config.debug else logging.NullHandler(),
            ]
        )
        
        # Push the main chat screen
        await self.push_screen(ChatScreen(self.config))
        
    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        # Main content will be handled by screens
        yield Footer()
        
    async def action_quit(self) -> None:
        """Handle force quit action (CTRL-Q)."""
        # Shutdown MCP services if available
        if hasattr(self.screen, 'mcp_client') and self.screen.mcp_client:
            await self.screen.mcp_client.shutdown()
        self.exit()
    
    def action_quit_with_confirmation(self) -> None:
        """Handle quit with confirmation (ESC)."""
        # Use a worker to handle the async modal - call the method to get the coroutine
        self.run_worker(self._quit_with_confirmation_worker(), exclusive=True)
    
    async def _quit_with_confirmation_worker(self) -> None:
        """Worker to handle quit confirmation dialog."""
        from .screens.confirmation import ConfirmationScreen
        
        try:
            # Show confirmation dialog
            confirmation = ConfirmationScreen("Really quit LIT TUI?")
            result = await self.push_screen_wait(confirmation)
            
            # Debug: Log what we got back
            import logging
            logging.info(f"Confirmation dialog result: {result} (type: {type(result)})")
            
            if result is True:
                # User confirmed, proceed with quit
                logging.info("User confirmed quit, proceeding...")
                await self.action_quit()
            else:
                logging.info("User cancelled quit, staying in app")
                # Small delay to prevent ESC key from being processed again immediately
                import asyncio
                await asyncio.sleep(0.1)
        except Exception as e:
            # If something goes wrong, just log it and don't quit
            import logging
            logging.error(f"Error in quit confirmation: {e}")
        
    async def action_new_chat(self) -> None:
        """Handle new chat action."""
        if hasattr(self.screen, 'new_chat'):
            await self.screen.new_chat()
            
    async def action_open_session(self) -> None:
        """Handle open session action."""
        if hasattr(self.screen, 'open_session'):
            await self.screen.open_session()
            
    async def action_help(self) -> None:
        """Show help screen."""
        # TODO: Implement help screen
        # For now, try to send to sidebar if available
        try:
            if hasattr(self.screen, 'notify_via_sidebar'):
                self.screen.notify_via_sidebar("Help screen coming soon!", "info")
            else:
                # Fallback for screens without sidebar
                pass
        except Exception:
            # Silently ignore if notification fails
            pass


def setup_argument_parser() -> argparse.ArgumentParser:
    """Set up command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="LIT TUI - Lightweight Terminal Chat Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lit-tui                          # Start with default settings
  lit-tui --model llama2          # Start with specific model
  lit-tui --debug                 # Enable debug logging
  lit-tui --config ~/.my-config   # Use custom config directory
        """
    )
    
    parser.add_argument(
        "--model", "-m",
        type=str,
        help="Default model to use (overrides config)"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Configuration directory path (default: ~/.lit-tui)"
    )
    
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"lit-tui {__import__('lit_tui').__version__}"
    )
    
    return parser


async def async_main(args: argparse.Namespace) -> int:
    """Async main function."""
    try:
        app = LitTuiApp(config_path=args.config)
        
        # Override config with command line args
        if args.debug:
            # This will be picked up during config loading
            pass
            
        await app.run_async()
        return 0
        
    except KeyboardInterrupt:
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


def main() -> int:
    """Main entry point."""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Run the async main function
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

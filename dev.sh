#!/bin/bash
# Quick development script for lit-tui
cd "$(dirname "$0")"
source .venv/bin/activate
echo "🚀 lit-tui development environment activated"
echo "💡 Available commands:"
echo "   lit-tui --help        # Show help"
echo "   lit-tui --debug       # Run with debug logging"
echo "   pytest                # Run tests"
echo "   black src/            # Format code"
echo "   mypy src/             # Type checking"
echo ""
bash

"""
Storage service for LIT TUI.

This module handles persistent storage of chat sessions, messages,
and application state using JSON files.
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import uuid4

import aiofiles

from ..config import Config


logger = logging.getLogger(__name__)


class ChatMessage:
    """Represents a chat message."""
    
    def __init__(
        self,
        role: str,
        content: str,
        timestamp: Optional[datetime] = None,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.model = model
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "model": self.model,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """Create from dictionary."""
        timestamp = datetime.fromisoformat(data["timestamp"])
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=timestamp,
            model=data.get("model"),
            metadata=data.get("metadata", {})
        )


class ChatSession:
    """Represents a chat session."""
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        created: Optional[datetime] = None,
        updated: Optional[datetime] = None,
        model: Optional[str] = None,
        messages: Optional[List[ChatMessage]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_saved: bool = False
    ):
        self.session_id = session_id or str(uuid4())
        self.title = title or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        self.created = created or datetime.now(timezone.utc)
        self.updated = updated or datetime.now(timezone.utc)
        self.model = model
        self.messages = messages or []
        self.metadata = metadata or {}
        self.is_saved = is_saved
    
    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the session."""
        self.messages.append(message)
        self.updated = datetime.now(timezone.utc)
        
        # Auto-generate title from first user message if not set
        if (self.title.startswith("Chat ") and 
            message.role == "user" and 
            len([m for m in self.messages if m.role == "user"]) == 1):
            self.title = self._generate_title(message.content)
    
    def _generate_title(self, content: str) -> str:
        """Generate a title from message content."""
        # Take first 50 characters and clean up
        title = content.strip()[:50]
        if len(content) > 50:
            title += "..."
        return title
    
    def get_message_count(self) -> Dict[str, int]:
        """Get count of messages by role."""
        counts = {"user": 0, "assistant": 0, "system": 0}
        for message in self.messages:
            if message.role in counts:
                counts[message.role] += 1
        return counts
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "model": self.model,
            "messages": [msg.to_dict() for msg in self.messages],
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        """Create from dictionary."""
        created = datetime.fromisoformat(data["created"])
        updated = datetime.fromisoformat(data["updated"])
        messages = [ChatMessage.from_dict(msg_data) for msg_data in data.get("messages", [])]
        
        return cls(
            session_id=data["session_id"],
            title=data["title"],
            created=created,
            updated=updated,
            model=data.get("model"),
            messages=messages,
            metadata=data.get("metadata", {}),
            is_saved=True  # Loaded sessions are by definition already saved
        )


class StorageService:
    """Service for managing persistent storage."""
    
    def __init__(self, config: Config, storage_dir: Optional[Path] = None):
        """Initialize storage service."""
        self.config = config
        self.storage_dir = storage_dir or Path.home() / ".lit-tui"
        self.sessions_dir = self.storage_dir / "sessions"
        self.settings_file = self.storage_dir / "settings.json"
        self.current_session: Optional[ChatSession] = None
        
        # Ensure directories exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_session(
        self,
        model: Optional[str] = None,
        title: Optional[str] = None
    ) -> ChatSession:
        """Create a new chat session (not saved to disk until first message)."""
        session = ChatSession(model=model, title=title, is_saved=False)
        self.current_session = session
        
        logger.info(f"Created new unsaved session: {session.session_id}")
        return session
    
    async def save_session(self, session: ChatSession) -> None:
        """Save a session to disk."""
        try:
            session_file = self.sessions_dir / f"{session.session_id}.json"
            session_data = session.to_dict()
            
            async with aiofiles.open(session_file, 'w') as f:
                await f.write(json.dumps(session_data, indent=2))
            
            # Mark session as saved
            session.is_saved = True
            
            if session_data.get("messages"):
                logger.debug(f"Saved session {session.session_id} with {len(session_data['messages'])} messages")
            else:
                logger.debug(f"Saved empty session {session.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")
            raise
    
    async def load_session(self, session_id: str) -> Optional[ChatSession]:
        """Load a session from disk."""
        try:
            session_file = self.sessions_dir / f"{session_id}.json"
            
            if not session_file.exists():
                logger.warning(f"Session file not found: {session_id}")
                return None
            
            async with aiofiles.open(session_file, 'r') as f:
                session_data = json.loads(await f.read())
            
            session = ChatSession.from_dict(session_data)
            logger.info(f"Loaded session: {session_id}")
            return session
            
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    async def list_sessions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List available sessions with metadata."""
        try:
            sessions = []
            
            for session_file in self.sessions_dir.glob("*.json"):
                try:
                    async with aiofiles.open(session_file, 'r') as f:
                        session_data = json.loads(await f.read())
                    
                    # Extract metadata for list view
                    sessions.append({
                        "session_id": session_data["session_id"],
                        "title": session_data["title"],
                        "created": session_data["created"],
                        "updated": session_data["updated"],
                        "model": session_data.get("model"),
                        "message_count": len(session_data.get("messages", []))
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to read session file {session_file}: {e}")
                    continue
            
            # Sort by updated time (most recent first)
            sessions.sort(key=lambda x: x["updated"], reverse=True)
            
            if limit:
                sessions = sessions[:limit]
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        try:
            session_file = self.sessions_dir / f"{session_id}.json"
            
            if session_file.exists():
                session_file.unlink()
                logger.info(f"Deleted session: {session_id}")
                return True
            else:
                logger.warning(f"Session file not found for deletion: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    async def cleanup_old_sessions(self, max_age_days: int = 30) -> int:
        """Clean up old sessions based on age."""
        try:
            cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_days * 24 * 3600)
            deleted_count = 0
            
            for session_file in self.sessions_dir.glob("*.json"):
                if session_file.stat().st_mtime < cutoff_time:
                    try:
                        session_file.unlink()
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete old session {session_file}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old sessions")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0
    
    async def export_session(self, session_id: str, export_path: Path) -> bool:
        """Export a session to a file."""
        try:
            session = await self.load_session(session_id)
            if not session:
                return False
            
            export_data = session.to_dict()
            
            async with aiofiles.open(export_path, 'w') as f:
                await f.write(json.dumps(export_data, indent=2))
            
            logger.info(f"Exported session {session_id} to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export session {session_id}: {e}")
            return False
    
    async def backup_storage(self, backup_path: Path) -> bool:
        """Create a backup of all storage."""
        try:
            shutil.copytree(self.storage_dir, backup_path, dirs_exist_ok=True)
            logger.info(f"Created storage backup at {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            session_files = list(self.sessions_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in session_files)
            
            return {
                "session_count": len(session_files),
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "storage_dir": str(self.storage_dir)
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {
                "session_count": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "storage_dir": str(self.storage_dir),
                "error": str(e)
            }
    
    async def save_last_model(self, model: str) -> None:
        """Save the last used model."""
        try:
            settings = await self.load_settings()
            settings["last_model"] = model
            
            async with aiofiles.open(self.settings_file, 'w') as f:
                await f.write(json.dumps(settings, indent=2))
            
            logger.debug(f"Saved last model: {model}")
            
        except Exception as e:
            logger.error(f"Failed to save last model: {e}")
    
    async def load_last_model(self) -> Optional[str]:
        """Load the last used model."""
        try:
            settings = await self.load_settings()
            return settings.get("last_model")
            
        except Exception as e:
            logger.error(f"Failed to load last model: {e}")
            return None
    
    async def load_settings(self) -> Dict[str, Any]:
        """Load user settings."""
        try:
            if self.settings_file.exists():
                async with aiofiles.open(self.settings_file, 'r') as f:
                    return json.loads(await f.read())
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            return {}

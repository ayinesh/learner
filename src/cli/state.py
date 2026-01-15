"""CLI State Management - Token storage and session state."""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID


@dataclass
class CLIState:
    """Current CLI session state."""

    user_id: Optional[UUID] = None
    email: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None

    @property
    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated."""
        if not self.access_token:
            return False
        if self.token_expires_at and self.token_expires_at < datetime.utcnow():
            return False
        return True


class StateManager:
    """Manages CLI state persistence."""

    def __init__(self) -> None:
        self._config_dir = self._get_config_dir()
        self._state_file = self._config_dir / "state.json"
        self._state: Optional[CLIState] = None

    def _get_config_dir(self) -> Path:
        """Get the configuration directory for the CLI."""
        # Use platform-appropriate config directory
        if os.name == "nt":  # Windows
            base = Path(os.environ.get("APPDATA", Path.home()))
        else:  # Unix-like
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

        config_dir = base / "learner"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def load(self) -> CLIState:
        """Load state from disk."""
        if self._state is not None:
            return self._state

        if not self._state_file.exists():
            self._state = CLIState()
            return self._state

        try:
            data = json.loads(self._state_file.read_text())
            self._state = CLIState(
                user_id=UUID(data["user_id"]) if data.get("user_id") else None,
                email=data.get("email"),
                access_token=data.get("access_token"),
                refresh_token=data.get("refresh_token"),
                token_expires_at=(
                    datetime.fromisoformat(data["token_expires_at"])
                    if data.get("token_expires_at")
                    else None
                ),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            self._state = CLIState()

        return self._state

    def save(self, state: CLIState) -> None:
        """Save state to disk with restricted permissions.

        Security: The state file contains sensitive tokens and is written
        with mode 0600 (read/write for owner only) on Unix systems.
        """
        self._state = state
        data = {
            "user_id": str(state.user_id) if state.user_id else None,
            "email": state.email,
            "access_token": state.access_token,
            "refresh_token": state.refresh_token,
            "token_expires_at": (
                state.token_expires_at.isoformat()
                if state.token_expires_at
                else None
            ),
        }

        # Write with restricted permissions (0600 on Unix)
        content = json.dumps(data, indent=2)

        if os.name != "nt":  # Unix-like systems
            # Create file with restricted permissions
            import stat
            # First write to temp file, then atomic rename
            temp_file = self._state_file.with_suffix('.tmp')
            try:
                # Remove temp file if it exists
                if temp_file.exists():
                    temp_file.unlink()

                # Create with restricted permissions
                fd = os.open(str(temp_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
                try:
                    os.write(fd, content.encode('utf-8'))
                finally:
                    os.close(fd)

                # Atomic rename
                temp_file.rename(self._state_file)
            except Exception:
                # Fallback to regular write if atomic write fails
                if temp_file.exists():
                    temp_file.unlink()
                self._state_file.write_text(content)
                # Set permissions after write
                os.chmod(str(self._state_file), stat.S_IRUSR | stat.S_IWUSR)
        else:
            # Windows - no chmod equivalent, but file is in user's AppData
            self._state_file.write_text(content)

    def clear(self) -> None:
        """Clear all state (logout)."""
        self._state = CLIState()
        if self._state_file.exists():
            self._state_file.unlink()

    def update_tokens(
        self,
        access_token: str,
        refresh_token: str,
        user_id: UUID,
        email: str,
        expires_in: int,
    ) -> None:
        """Update authentication tokens."""
        from datetime import timedelta

        state = self.load()
        state.user_id = user_id
        state.email = email
        state.access_token = access_token
        state.refresh_token = refresh_token
        state.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        self.save(state)


# Singleton instance
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get state manager singleton."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def require_auth() -> CLIState:
    """Require authentication and return current state.

    Raises:
        SystemExit: If not authenticated
    """
    import typer
    from rich.console import Console

    console = Console()
    state = get_state_manager().load()

    if not state.is_authenticated:
        console.print("[red]Error:[/red] Not authenticated. Please run 'learner auth login' first.")
        raise typer.Exit(1)

    return state


def get_current_user_id() -> UUID:
    """Get current user ID or raise if not authenticated."""
    state = require_auth()
    if state.user_id is None:
        raise ValueError("User ID not available")
    return state.user_id

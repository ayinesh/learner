"""CLI Commands - Command group modules."""

from src.cli.commands.auth import auth_app
from src.cli.commands.learn import learn_app
from src.cli.commands.profile import profile_app
from src.cli.commands.content import content_app
from src.cli.commands.stats import stats_app

__all__ = [
    "auth_app",
    "learn_app",
    "profile_app",
    "content_app",
    "stats_app",
]

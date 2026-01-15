"""CLI Module - Command-line interface for the Learner application.

This module provides a rich interactive CLI built with Typer and Rich.

Usage:
    learner --help              Show all commands
    learner auth login          Log in to your account
    learner profile onboarding  Complete initial setup
    learner start               Start a learning session
    learner quiz                Take a quick quiz
    learner explain <topic>     Test understanding with Feynman technique
    learner stats progress      View learning progress
"""

from src.cli.main import app, main

__all__ = ["app", "main"]

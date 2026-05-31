"""Oasis AI service package."""

from .app import app, create_app
from .models import Spec

__all__ = ["Spec", "app", "create_app"]

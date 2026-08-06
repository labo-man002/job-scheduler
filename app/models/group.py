"""Backward-compatible import for the renamed institute entity."""

from app.models.institute import Institute

Group = Institute

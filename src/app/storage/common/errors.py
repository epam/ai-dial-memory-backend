"""Shared error types for the storage module public interface."""
from __future__ import annotations


class RowNotFoundError(Exception):
    """Raised when a requested memory row does not exist."""


class StorageSyncError(Exception):
    """Raised when pulling or pushing the remote dataset fails."""

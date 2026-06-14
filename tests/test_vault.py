"""Tests for the vault module."""

import os
import tempfile
from pathlib import Path

import pytest

from bfai.config import VAULT_SUBDIRS, get_vault_path
from bfai.vault import ensure_vault, get_vault


class TestGetVaultPath:
    """Tests for vault path resolution."""

    def test_default_path(self):
        """Default vault path should be ./vault/ relative to CWD."""
        path = get_vault_path()
        expected = Path("./vault").resolve()
        assert path == expected

    def test_env_var_override(self):
        """BFAI_VAULT_PATH env var should override the default path."""
        test_path = "/tmp/bfai-test-vault"
        os.environ["BFAI_VAULT_PATH"] = test_path
        try:
            path = get_vault_path()
            assert str(path) == test_path
        finally:
            del os.environ["BFAI_VAULT_PATH"]

    def test_env_var_relative_path(self):
        """Relative env var path should be resolved to absolute."""
        os.environ["BFAI_VAULT_PATH"] = "./custom_vault"
        try:
            path = get_vault_path()
            assert path.is_absolute()
            assert path.name == "custom_vault"
        finally:
            del os.environ["BFAI_VAULT_PATH"]


class TestEnsureVault:
    """Tests for vault initialization."""

    def test_ensure_vault_creates_directories(self):
        """ensure_vault should create vault root and all subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "test_vault"
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                result = ensure_vault()

                assert result == vault_path
                assert vault_path.exists()
                assert vault_path.is_dir()

                for subdir in VAULT_SUBDIRS:
                    subdir_path = vault_path / subdir
                    assert subdir_path.exists(), f"Subdirectory {subdir} was not created"
                    assert subdir_path.is_dir()
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_ensure_vault_idempotent(self):
        """Calling ensure_vault multiple times should not raise errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "test_vault"
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                ensure_vault()
                ensure_vault()  # Second call should succeed
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_get_vault_without_ensure(self):
        """get_vault should return the path without creating directories."""
        path = get_vault()
        assert isinstance(path, Path)
        # Should not have created the directory
        assert not path.exists() or path == get_vault_path()


class TestVaultSubdirs:
    """Tests for vault subdirectory constants."""

    def test_vault_subdirs_defined(self):
        """VAULT_SUBDIRS should contain the expected directories."""
        assert "notes" in VAULT_SUBDIRS
        assert "images" in VAULT_SUBDIRS
        assert "documents" in VAULT_SUBDIRS
        assert "metadata" in VAULT_SUBDIRS

    def test_vault_subdirs_no_duplicates(self):
        """VAULT_SUBDIRS should not contain duplicates."""
        assert len(VAULT_SUBDIRS) == len(set(VAULT_SUBDIRS))
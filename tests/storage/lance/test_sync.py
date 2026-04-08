"""Tests for StorageSync — directory pack/unpack via tar.gz."""
from __future__ import annotations

import io
import tarfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.dial.dial_storage import DialStorageError, DialStorageService
from src.app.storage.lance.sync import StorageSync


def _make_fake_lance_dir(base: Path) -> Path:
    """Populate a fake memory.lance directory tree like LanceDB would create."""
    lance = base / "memory.lance"
    lance.mkdir(parents=True)
    (lance / "_versions").mkdir()
    (lance / "_versions" / "0.manifest").write_bytes(b"manifest")
    (lance / "data").mkdir()
    (lance / "data" / "chunk.lance").write_bytes(b"rows")
    return lance


def _make_sync(tmp_path: Path) -> tuple[StorageSync, AsyncMock]:
    dial = AsyncMock(spec=DialStorageService)
    dial.get_storage_home.return_value = "files/user123"
    settings = MagicMock()
    settings.tmp_dir = tmp_path
    return StorageSync(dial, settings), dial


# ---------------------------------------------------------------------------
# _sync_up
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_up_uploads_tar_gz_not_raw_directory(tmp_path: Path) -> None:
    """_sync_up must pack the lance directory into a .tar.gz before uploading."""
    lance = _make_fake_lance_dir(tmp_path / "bucket")
    sync, dial = _make_sync(tmp_path)

    captured: dict[str, bytes] = {}

    async def _fake_upload(api_key: str, local_path: Path, remote_url: str) -> None:
        captured[remote_url] = local_path.read_bytes()

    dial.upload.side_effect = _fake_upload

    await sync._sync_up("key", "files/user123", lance)

    assert len(captured) == 1
    remote_url, raw = next(iter(captured.items()))
    assert remote_url.endswith("memory.tar.gz"), (
        f"Expected .tar.gz remote URL, got {remote_url!r}"
    )

    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
        names = tar.getnames()

    assert any(n.startswith("memory.lance") for n in names), (
        f"tar archive did not contain memory.lance entries: {names}"
    )


@pytest.mark.asyncio
async def test_sync_up_cleans_up_temp_tar(tmp_path: Path) -> None:
    """The temporary .tar.gz file must be removed after upload."""
    lance = _make_fake_lance_dir(tmp_path / "bucket")
    sync, dial = _make_sync(tmp_path)

    await sync._sync_up("key", "files/user123", lance)

    leftover = list((tmp_path / "bucket").glob("*.tar.gz"))
    assert leftover == [], f"Temp tar.gz was not cleaned up: {leftover}"


# ---------------------------------------------------------------------------
# _sync_down
# ---------------------------------------------------------------------------


def _make_tar_gz(source_dir: Path) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(source_dir, arcname="memory.lance")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_sync_down_extracts_tar_gz_to_lance_dir(tmp_path: Path) -> None:
    """_sync_down must download a .tar.gz and extract it to the local lance path."""
    # Prepare tar.gz content simulating what _sync_up would have stored.
    src = tmp_path / "src_lance"
    src.mkdir()
    (src / "sentinel.txt").write_bytes(b"hello")
    tar_bytes = _make_tar_gz(src)

    dest_base = tmp_path / "bucket"
    dest_base.mkdir()
    local_lance = dest_base / "memory.lance"

    sync, dial = _make_sync(tmp_path)

    async def _fake_download(api_key: str, remote_url: str, local_path: Path) -> None:
        local_path.write_bytes(tar_bytes)

    dial.download.side_effect = _fake_download

    await sync._sync_down("key", "files/user123", local_lance)

    assert local_lance.is_dir(), "memory.lance should be a directory after extraction"
    assert (local_lance / "sentinel.txt").read_bytes() == b"hello"


@pytest.mark.asyncio
async def test_sync_down_leaves_no_lance_dir_on_404(tmp_path: Path) -> None:
    """When the remote is missing (404), _sync_down must NOT create memory.lance/.

    LanceDB must own that directory — pre-creating it as empty causes LanceDB
    to see a corrupt table and raise 'Table not found'.
    Only the parent dir is created so LanceDB can init cleanly.
    """
    local_lance = tmp_path / "bucket" / "memory.lance"
    sync, dial = _make_sync(tmp_path)

    dial.download.side_effect = DialStorageError("404 not found")

    await sync._sync_down("key", "files/user123", local_lance)

    assert not local_lance.exists(), "memory.lance must not be pre-created on 404"
    assert local_lance.parent.is_dir(), "parent dir must exist so LanceDB can write into it"


@pytest.mark.asyncio
async def test_sync_down_cleans_up_temp_tar(tmp_path: Path) -> None:
    """The downloaded .tar.gz temp file must be removed after extraction."""
    src = tmp_path / "src"
    src.mkdir()
    tar_bytes = _make_tar_gz(src)

    dest_base = tmp_path / "bucket"
    dest_base.mkdir()
    local_lance = dest_base / "memory.lance"

    sync, dial = _make_sync(tmp_path)

    async def _fake_download(api_key: str, remote_url: str, local_path: Path) -> None:
        local_path.write_bytes(tar_bytes)

    dial.download.side_effect = _fake_download

    await sync._sync_down("key", "files/user123", local_lance)

    leftover = list(dest_base.glob("*.tar.gz"))
    assert leftover == [], f"Temp tar.gz was not cleaned up: {leftover}"

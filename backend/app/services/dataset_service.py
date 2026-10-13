"""Dataset availability + upload service.

The pipeline resolves a dataset by *filename* — see
:func:`app.engine.tools.ml.resolve_dataset_path`, which looks in this order:

1. an explicit ``dataset_path``,
2. a file in ``settings.UPLOAD_DIR``,
3. object storage via a ``datasets`` row matching ``original_filename``.

Step 2 is checked before any database or storage work, so writing an uploaded
file into ``UPLOAD_DIR`` is sufficient to make a dataset resolvable by the
worker. This module exposes that same resolution to the API so the UI can ask
"is this dataset available?" *before* a run is queued, instead of letting the
worker fail with :class:`~app.engine.tools.ml.DatasetNotFoundError` after the
user has already waited for the pipeline to start.

Note on :class:`~app.models.dataset.Dataset` rows: they require a non-null
``project_id``, so uploading through this service deliberately does not create
one. A file in the upload directory is enough for resolution, and inventing a
project row per upload would be misleading.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.file_upload import get_safe_filepath
from app.models.dataset import Dataset
from app.models.workspace import Workspace


def _upload_dir() -> Path:
    from app.core.config import settings

    return Path(settings.UPLOAD_DIR)


def sanitize_dataset_name(name: str) -> str:
    """Reduce a user-supplied dataset name to a bare, safe basename.

    The pipeline joins the name straight onto the upload directory, so
    anything that could escape that directory (``../``, absolute paths, nested
    separators) is stripped rather than rejected — the user almost always
    means the basename.
    """
    from app.core.file_upload import sanitize_filename

    cleaned = (name or "").strip().replace("\\", "/")
    cleaned = cleaned.rsplit("/", 1)[-1]
    return sanitize_filename(cleaned)


async def resolve_for_user(
    session: AsyncSession,
    owner_id: UUID,
    name: str,
    workspace_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    """Report whether ``name`` resolves for ``owner_id``.

    Mirrors the worker's resolution order: the local upload directory first,
    then a ``datasets`` row owned by one of the caller's workspaces. Rows from
    other users are never considered, so the probe cannot be used to discover
    another tenant's filenames.
    """
    safe_name = sanitize_dataset_name(name)
    if not safe_name:
        return {"name": name, "available": False, "source": None, "size_bytes": None}

    local = _upload_dir() / safe_name
    if local.is_file():
        return {
            "name": safe_name,
            "available": True,
            "source": "upload_dir",
            "size_bytes": local.stat().st_size,
        }

    # Scope the registry lookup to workspaces this user owns.
    stmt = (
        select(Dataset)
        .join(Workspace, Dataset.workspace_id == Workspace.id)
        .where(
            Workspace.owner_id == owner_id,
            Dataset.original_filename == safe_name,
        )
        .order_by(Dataset.updated_at.desc())
        .limit(1)
    )
    if workspace_id is not None:
        stmt = stmt.where(Dataset.workspace_id == workspace_id)

    row = (await session.execute(stmt)).scalars().first()
    if row is None:
        return {"name": safe_name, "available": False, "source": None, "size_bytes": None}
    return {
        "name": safe_name,
        "available": True,
        "source": "registry",
        "size_bytes": row.file_size_bytes,
        "dataset_id": str(row.id),
    }


async def list_for_user(
    session: AsyncSession,
    owner_id: UUID,
    workspace_id: Optional[UUID] = None,
) -> List[Dict[str, Any]]:
    """List the datasets this user can actually resolve, by filename."""
    stmt = (
        select(Dataset)
        .join(Workspace, Dataset.workspace_id == Workspace.id)
        .where(Workspace.owner_id == owner_id)
        .order_by(Dataset.updated_at.desc())
    )
    if workspace_id is not None:
        stmt = stmt.where(Dataset.workspace_id == workspace_id)

    rows = (await session.execute(stmt)).scalars().all()
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for row in rows:
        if row.original_filename in seen:
            continue
        seen.add(row.original_filename)
        out.append(
            {
                "name": row.original_filename,
                "size_bytes": row.file_size_bytes,
                "dataset_id": str(row.id),
            }
        )
    return out


def store_upload(filename: str, content: bytes) -> Dict[str, Any]:
    """Write ``content`` into the upload directory under ``filename``.

    Synchronous by design — it is a small bounded write (size already capped
    by ``read_file_with_limit``) and it keeps the file exactly where
    :func:`app.engine.tools.ml.resolve_dataset_path` looks for it.
    """
    safe_name = sanitize_dataset_name(filename)
    path = get_safe_filepath(str(_upload_dir()), safe_name)
    with open(path, "wb") as fh:
        fh.write(content)
    return {"name": safe_name, "size_bytes": len(content), "path": path}
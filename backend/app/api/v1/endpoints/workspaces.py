"""Workspace endpoints (Phase 3/4).

Workspaces are the top-level isolation boundary for experiments. Minimal
surface on purpose: create, list (paginated), and read — all owner-scoped
(401 without credentials, 404 for foreign workspaces).
"""
from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession, OwnedWorkspace
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceRead,
)
from app.services import workspace_service

router = APIRouter()


@router.post(
    "",
    response_model=WorkspaceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace",
)
async def create_workspace(
    payload: WorkspaceCreate, user: CurrentUser, session: DbSession
) -> WorkspaceRead:
    workspace = await workspace_service.create_for_user(session, user.id, payload)
    return WorkspaceRead.model_validate(workspace)


@router.get("", response_model=WorkspaceListResponse, summary="List my workspaces")
async def list_workspaces(
    user: CurrentUser,
    session: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> WorkspaceListResponse:
    items, total = await workspace_service.list_for_user(
        session, user.id, page=page, page_size=page_size
    )
    return WorkspaceListResponse(
        items=[WorkspaceRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{workspace_id}", response_model=WorkspaceRead, summary="Get my workspace")
async def get_workspace(workspace: OwnedWorkspace) -> WorkspaceRead:
    return WorkspaceRead.model_validate(workspace)

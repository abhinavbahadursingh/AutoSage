"""Project endpoints with user/workspace isolation (Phase 2).

Every route requires a valid Better Auth JWT. Users only ever see and mutate
their own projects; cross-user access returns 404 so ids cannot be enumerated.
"""
from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession, OwnedProject
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services import project_service

router = APIRouter()


@router.get("", response_model=list[ProjectResponse], summary="List my projects")
@router.get("/", response_model=list[ProjectResponse], include_in_schema=False)
async def list_projects(user: CurrentUser, session: DbSession) -> list[ProjectResponse]:
    projects = await project_service.list_for_user(session, user.id)
    return [ProjectResponse.model_validate(project) for project in projects]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project in my workspace",
)
@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_project(
    payload: ProjectCreate, user: CurrentUser, session: DbSession
) -> ProjectResponse:
    project = await project_service.create_for_user(session, user.id, payload)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get my project")
async def get_project(project: OwnedProject) -> ProjectResponse:
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse, summary="Update my project")
async def update_project(
    payload: ProjectUpdate, project: OwnedProject, session: DbSession
) -> ProjectResponse:
    updated = await project_service.update_for_user(session, project.id, project.user_id, payload)
    return ProjectResponse.model_validate(updated)


@router.delete("/{project_id}", summary="Delete my project")
async def delete_project(project: OwnedProject, session: DbSession) -> Response:
    await project_service.delete_for_user(session, project.id, project.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

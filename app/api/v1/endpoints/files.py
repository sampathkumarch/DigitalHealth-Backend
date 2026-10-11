from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, RedirectResponse

from app.api.deps import get_file_service, get_optional_user
from app.core.exceptions import NotFoundError
from app.domain.users import UserAccount
from app.services.files import FileService

router = APIRouter()


@router.get("/{file_id}/content", response_model=None)
def download_file(
    file_id: UUID,
    access: str | None = None,
    user: UserAccount | None = Depends(get_optional_user),
    service: FileService = Depends(get_file_service),
) -> FileResponse | RedirectResponse:
    content = service.open(
        file_id,
        user_id=user.id if user else None,
        access_token=access,
    )
    if content.redirect_url:
        return RedirectResponse(content.redirect_url)
    if not content.local_path:
        raise NotFoundError("File not found")
    return FileResponse(
        content.local_path,
        media_type=content.content_type,
        filename=content.filename,
    )

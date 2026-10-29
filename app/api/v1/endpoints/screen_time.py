from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_screen_time_service
from app.domain.users import UserAccount
from app.schemas.screen_time import (
    ReplaceScreenTimeRequest,
    ScreenTimeDaysResponse,
    ScreenTimeSpanResponse,
    days_response,
    drafts_from_request,
)
from app.services.screen_time import ScreenTimeService

router = APIRouter(prefix="/me/screen-time", tags=["screen-time"])


@router.get("/span", response_model=ScreenTimeSpanResponse)
def day_span(
    device_id: UUID,
    user: UserAccount = Depends(get_current_user),
    service: ScreenTimeService = Depends(get_screen_time_service),
) -> ScreenTimeSpanResponse:
    origin, last, stored_device = service.day_span(user.id, device_id)
    return ScreenTimeSpanResponse(origin_date=origin, last_date=last, device_id=stored_device)


@router.put("/days", response_model=ScreenTimeDaysResponse)
def replace_days(
    body: ReplaceScreenTimeRequest,
    user: UserAccount = Depends(get_current_user),
    service: ScreenTimeService = Depends(get_screen_time_service),
) -> ScreenTimeDaysResponse:
    stored = service.replace_days(user.id, drafts_from_request(body))
    return days_response(stored)


@router.get("", response_model=ScreenTimeDaysResponse)
def list_days(
    device_id: UUID,
    day_from: date = Query(alias="from"),
    day_to: date = Query(alias="to"),
    user: UserAccount = Depends(get_current_user),
    service: ScreenTimeService = Depends(get_screen_time_service),
) -> ScreenTimeDaysResponse:
    return days_response(service.list_days(user.id, device_id, day_from, day_to))

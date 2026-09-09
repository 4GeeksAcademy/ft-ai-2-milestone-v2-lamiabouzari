"""Profile routes."""

import uuid

from fastapi import APIRouter, Depends, status
from tinydb import Query

from database import get_db
from dependencies import get_current_user
from exceptions import AppException, forbidden, invalid_user_id
from models.profile import Profile, ProfilePublic, ProfileUpdate
from models.user import User, UserRole

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _parse_user_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise invalid_user_id()


@router.get("/me", response_model=ProfilePublic)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    profiles = db.table("profiles")
    ProfileQuery = Query()

    profile_data = profiles.get(ProfileQuery.user_id == str(current_user.id))

    if not profile_data:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
            error_code="USER_NOT_FOUND",
        )

    return Profile(**profile_data)


@router.put("/me", response_model=ProfilePublic)
def update_my_profile(
    profile_update: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    profiles = db.table("profiles")
    ProfileQuery = Query()

    profile_data = profiles.get(ProfileQuery.user_id == str(current_user.id))

    if not profile_data:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
            error_code="USER_NOT_FOUND",
        )

    updates = profile_update.model_dump(exclude_none=True)

    profiles.update(
        updates,
        ProfileQuery.user_id == str(current_user.id),
    )

    updated_profile = profiles.get(
        ProfileQuery.user_id == str(current_user.id)
    )

    return Profile(**updated_profile)


@router.get("", response_model=list[ProfilePublic])
def list_profiles(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    if current_user.role != UserRole.admin:
        raise forbidden()

    profiles = db.table("profiles")
    return [Profile(**profile_data) for profile_data in profiles.all()]


@router.get("/{user_id}", response_model=ProfilePublic)
def get_profile_by_user_id(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    target_user_id = _parse_user_id(user_id)

    is_admin = current_user.role == UserRole.admin
    if current_user.id != target_user_id and not is_admin:
        raise forbidden()

    profiles = db.table("profiles")
    ProfileQuery = Query()

    profile_data = profiles.get(ProfileQuery.user_id == str(target_user_id))

    if not profile_data:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
            error_code="USER_NOT_FOUND",
        )

    return Profile(**profile_data)


@router.put("/{user_id}", response_model=ProfilePublic)
def update_profile_by_user_id(
    user_id: str,
    profile_update: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    target_user_id = _parse_user_id(user_id)

    is_admin = current_user.role == UserRole.admin
    if current_user.id != target_user_id and not is_admin:
        raise forbidden()

    profiles = db.table("profiles")
    ProfileQuery = Query()

    profile_data = profiles.get(ProfileQuery.user_id == str(target_user_id))

    if not profile_data:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
            error_code="USER_NOT_FOUND",
        )

    updates = profile_update.model_dump(exclude_none=True)

    profiles.update(
        updates,
        ProfileQuery.user_id == str(target_user_id),
    )

    updated_profile = profiles.get(ProfileQuery.user_id == str(target_user_id))

    return Profile(**updated_profile)
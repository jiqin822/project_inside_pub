"""Config push and reload (config file master over env; push overrides at runtime)."""
from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.domain.admin.models import User
from app.settings import get_config_store

router = APIRouter()


@router.post("/config", status_code=status.HTTP_200_OK)
async def update_config(
    body: dict = Body(..., embed=False),
    current_user: User = Depends(get_current_user),
):
    """
    Push config overrides at runtime. Merges into in-memory overrides; config file remains master over env.
    Use get_settings() or the settings proxy to read latest values. Validation errors keep previous config.
    """
    try:
        get_config_store().update(body)
        return {"ok": True, "message": "Config updated"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Config update failed: {e}",
        )


@router.post("/config/reload", status_code=status.HTTP_200_OK)
async def reload_config(
    current_user: User = Depends(get_current_user),
):
    """Re-read the config file and reapply saved overrides. File remains master over env."""
    try:
        get_config_store().reload_from_file()
        return {"ok": True, "message": "Config reloaded from file"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Config reload failed: {e}",
        )


@router.post("/config/clear-overrides", status_code=status.HTTP_200_OK)
async def clear_config_overrides(
    current_user: User = Depends(get_current_user),
):
    """Drop pushed overrides and reset to config file (master) + env."""
    get_config_store().clear_overrides()
    return {"ok": True, "message": "Overrides cleared"}

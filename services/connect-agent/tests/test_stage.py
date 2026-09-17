import pytest

from app.stage import StageError, stage_on_platform


@pytest.mark.asyncio
async def test_stage_rejects_unknown_platform() -> None:
    class _Page:
        pass

    with pytest.raises(StageError, match="not supported"):
        await stage_on_platform(_Page(), "tiktok", "caption", None)  # type: ignore[arg-type]

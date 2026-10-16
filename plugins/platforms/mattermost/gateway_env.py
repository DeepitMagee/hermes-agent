"""Mattermost env -> gateway config bridge (``PlatformEntry.env_overrides``)."""

from gateway.config import Platform
from gateway.platform_env import EnvCred, home_step

ENV_ENABLE_CREDENTIALS = ("MATTERMOST_TOKEN",)
ENV_OVERRIDES = (
    EnvCred(
        Platform.MATTERMOST, ("MATTERMOST_TOKEN",), token="MATTERMOST_TOKEN",
        warn_missing=("MATTERMOST_URL", "MATTERMOST_TOKEN set but MATTERMOST_URL is missing"),
        fixed=(("url", "MATTERMOST_URL"),),
    ),
    home_step(Platform.MATTERMOST, "MATTERMOST_HOME_CHANNEL"),
)

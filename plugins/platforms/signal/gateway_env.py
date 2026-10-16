"""Signal env -> gateway config bridge (``PlatformEntry.env_overrides``)."""

from gateway.config import Platform
from gateway.platform_env import EnvCred, home_step
from utils import is_truthy_value

ENV_ENABLE_CREDENTIALS = ("SIGNAL_HTTP_URL",)
ENV_OVERRIDES = (
    EnvCred(
        Platform.SIGNAL, ("SIGNAL_HTTP_URL", "SIGNAL_ACCOUNT"),
        fixed=(
            ("http_url", "SIGNAL_HTTP_URL"), ("account", "SIGNAL_ACCOUNT"),
            ("ignore_stories", "SIGNAL_IGNORE_STORIES", "true", is_truthy_value),
        ),
    ),
    home_step(Platform.SIGNAL, "SIGNAL_HOME_CHANNEL"),
)

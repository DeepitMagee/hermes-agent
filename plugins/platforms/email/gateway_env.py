"""Email env -> gateway config bridge (``PlatformEntry.env_overrides``)."""

from gateway.config import Platform
from gateway.platform_env import EnvCred, home_step

ENV_ENABLE_CREDENTIALS = ("EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_IMAP_HOST", "EMAIL_SMTP_HOST")
ENV_OVERRIDES = (
    EnvCred(
        Platform.EMAIL, ("EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_IMAP_HOST", "EMAIL_SMTP_HOST"),
        fixed=(("address", "EMAIL_ADDRESS"), ("imap_host", "EMAIL_IMAP_HOST"), ("smtp_host", "EMAIL_SMTP_HOST")),
    ),
    home_step(Platform.EMAIL, "EMAIL_HOME_ADDRESS"),
)

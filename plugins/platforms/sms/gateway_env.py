"""SMS (Twilio) env -> gateway config bridge (``PlatformEntry.env_overrides``)."""

from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.platform_env import EnvCred, getenv, home_step


def _api_key(config: GatewayConfig, sms_config: PlatformConfig) -> None:
    sms_config.api_key = getenv("TWILIO_AUTH_TOKEN")


ENV_ENABLE_CREDENTIALS = ("TWILIO_ACCOUNT_SID",)
ENV_OVERRIDES = (
    EnvCred(Platform.SMS, ("TWILIO_ACCOUNT_SID",), then=_api_key),
    home_step(Platform.SMS, "SMS_HOME_CHANNEL"),
)

from __future__ import annotations

from omni_cio.web.telegram_oidc_v1 import TelegramOidcRuntimeV1
from omni_cio.web.vk_id_oauth_v1 import VkIdOauthRuntimeV1


class BrowserBoundTelegramOidcRuntimeV1(TelegramOidcRuntimeV1):
    """Deployed Telegram runtime using the shared route-owned proof contract."""


class BrowserBoundVkIdOauthRuntimeV1(VkIdOauthRuntimeV1):
    """Deployed VK ID runtime using the shared route-owned proof contract."""

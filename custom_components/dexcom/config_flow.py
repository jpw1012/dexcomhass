import logging
from homeassistant import config_entries
# from .const import DOMAIN
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DATE,
    CONF_SCAN_INTERVAL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
    CONF_FRIENDLY_NAME
)

DOMAIN = "dexcom"
URL_ROOT = "sandbox-api.dexcom.com"

_LOGGER = logging.getLogger(DOMAIN)


class DexcomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, info):
        _LOGGER.info("Starting init step")
        if info is not None:
            self.init_info = info
            return await self.async_step_authorize()

        return self.async_show_form(
            step_id="authorize", data_schema=vol.Schema(
                {
                    vol.Required("friendly_name"): str,
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str
                }
            )
        )

    async def async_step_authorize(self, user_input=None):
        if user_input is None:
            info = self.init_info
            return self.async_external_step(
                step_id="user",
                url=f"{URL_ROOT}/v2/oauth2/login?client_id={info[CONF_CLIENT_ID]}&response_type=code&scope=offline_access&state={self.flow_id}&config_flow_id={self.flow_id}",
            )
        self.auth_info = user_input
        return self.async_external_step_done(next_step_id="finish")

    async def async_step_finish(self, user_input=None):
        _LOGGER.info(f"made it! {self.auth_info}")

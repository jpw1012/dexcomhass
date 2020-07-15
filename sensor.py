"""Sensor for Dexcom packages."""
import logging
import json
from json import JSONEncoder
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_SCAN_INTERVAL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle, slugify
from homeassistant.util.dt import now, parse_date
from homeassistant.helpers.network import get_url
from homeassistant.helpers.storage import Store

import http.client
import mimetypes

_LOGGER = logging.getLogger(__name__)

DOMAIN = "dexcom"
URLROOT = "sandbox-api.dexcom.com"
ICON = "mdi:spoon-sugar"
STOREKEY = "dexcom"

DATEFORMAT = "%Y-%m-%dT%H:%M:%S"

SCAN_INTERVAL = timedelta(seconds=300)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Required(CONF_TOKEN): cv.string
    }
)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    from dexcomapi import DexcomSession

    try:
        client_id = config.get(CONF_CLIENT_ID)
        client_secret = config.get(CONF_CLIENT_SECRET)
        refresh = config.get(CONF_TOKEN)

        # Get storage to see if we have a newer refresh token.
        store = get_store(hass, 1)
        token_data = await store.async_load()
        if token_data is not None and "refresh_token" in token_data:
            refresh = token_data["refresh_token"]

        url = get_url(hass, require_ssl=True, allow_internal=False)
        _LOGGER.info("Starting Dexcom session")
        _session = DexcomSession(url, client_id, client_secret, refresh)
        # first try to load tokens from storage

    except:
        _LOGGER.exception("Could not connect to Dexcom")
        return False

    async_add_entities(
        [
            BGSensor(
                _session,
                store,
                config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
            )
        ],
        True,
    )


def get_store(hass, version):
    store = Store(hass, version, STOREKEY, encoder=JSONEncoder, private=True)
    return store


async def save_token(store, token):
    await store.async_save(token)


class BGSensor(Entity):
    """Blood Glucose Sensor."""

    def __init__(self, session, store, interval):
        """Initialize the sensor."""
        self._session = session
        self._attributes = None
        self._state = None
        self._store = store
        self.async_update = Throttle(interval)(self._update)

    @property
    def name(self):
        """Return the name of the sensor."""
        return DOMAIN

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "mg/dl"

    async def try_update(self):
        try:
            bg = await self.hass.async_add_executor_job(self._session.load_current_bg)
            self._attributes = {ATTR_ATTRIBUTION: DOMAIN}
            self._attributes.update(bg)
            self._state = bg["smoothedValue"]
            return True
        except Exception as e:
            _LOGGER.info("Failed to update data")
            raise e

    async def _update(self):
        from dexcomapi import ExpiredSessionException
        """Update device state."""
        _LOGGER.info("Updating Dexcom")
        retry_count = 0
        do_retry = True

        while do_retry and retry_count < 3:  # MaxRetry = 3
            try:
                do_retry = False
                res = await self.try_update()
            except ExpiredSessionException as ex:
                # Reload session and persist new token
                _LOGGER.info("Session expired so refresh and retry")
                do_retry = True
                retry_count += 1
                res = await self.hass.async_add_executor_job(self._session.load_session)
                self.hass.async_create_task(save_token(self._store, res))
            except Exception as e:
                _LOGGER.error("Error while updating data")
                _LOGGER.error(e)
                raise e

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

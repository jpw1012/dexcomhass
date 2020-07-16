"""Sensor for Dexcom packages."""
import logging
from json import JSONEncoder
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DATE,
    CONF_SCAN_INTERVAL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
    CONF_FRIENDLY_NAME
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.helpers.network import get_url
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)
ICON = "mdi:spoon-sugar"
STOREKEY = "dexcom"

DATEFORMAT = "%Y-%m-%dT%H:%M:%S"

SCAN_INTERVAL = timedelta(seconds=300)

DOMAIN = "dexcom"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FRIENDLY_NAME): cv.string,
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
        name = config.get(CONF_FRIENDLY_NAME)

        # Get storage to see if we have a newer refresh token.
        store = get_store(hass, 1)
        token_data = await store.async_load()
        if token_data is not None and "refresh_token" in token_data:
            refresh = token_data["refresh_token"]

        url = get_url(hass, require_ssl=True, allow_internal=False)
        _LOGGER.info("Starting Dexcom session")
        _session = DexcomSession(name, url, client_id, client_secret, refresh)
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
        self._missing_data_count = 0
        self._available = True
        self.async_update = Throttle(interval)(self._update)

    @property
    def available(self):
        # Is the sensor available? Return false if marked unavailable or if missed data 4 times ina row (~20 minutes)
        return self._available and self._missing_data_count < 4

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._session.get_name() + "_BG"

    @property
    def unique_id(self):
        """Return the unique name of the sensor."""
        return DOMAIN+"_BG-"+self._session.get_name()

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
            self._attributes = {ATTR_ATTRIBUTION: DOMAIN,
                                ATTR_DATE: bg["displayTime"] }
            self._attributes.update(bg)
            self._state = bg["smoothedValue"]
            return True
        except Exception as e:
            _LOGGER.info("Failed to update data")
            raise e

    async def _update(self):
        from dexcomapi import ExpiredSessionException, NoBGDataException
        """Update device state."""
        _LOGGER.info("Updating Dexcom")
        retry_count = 0
        do_retry = True

        while do_retry and retry_count < 3:  # MaxRetry = 3
            try:
                do_retry = False
                res = await self.try_update()
                if res:
                    self._missing_data_count = 0
                    self._available = True
                    _LOGGER.info("Successfully refreshed data!")

            except ExpiredSessionException as ex:
                # Reload session and persist new token
                _LOGGER.info("Session expired so refresh and retry")
                do_retry = True
                retry_count += 1
                res = await self.hass.async_add_executor_job(self._session.load_session)
                self.hass.async_create_task(save_token(self._store, res))
            except NoBGDataException as nd_ex:
                # no data was found. Could be a bad signal or just a restarting cgm. Note it and move on.
                # Mimicking the cgm behavior, a single missed entry does not mean an error
                self._missing_data_count += 1

            except Exception as e:
                _LOGGER.error("Error while updating data")
                _LOGGER.error(e)
                self._available = False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

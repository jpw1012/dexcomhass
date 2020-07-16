"""Dexcom api sensor"""
import logging

DOMAIN = "hello_service"

ATTR_NAME = "name"
DEFAULT_NAME = "World"
_LOGGER = logging.getLogger(DOMAIN)


def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""

    def handle_hello(call):
        """Handle the service call."""
        name = call.data.get(ATTR_NAME, DEFAULT_NAME)

        _LOGGER.info(f"Got it! {call.data}")

    hass.services.register(DOMAIN, "test", handle_hello)

    # Return boolean to indicate that initialization was successfully.
    return True

"""Fake AI task + STT for testing the recipes integration offline."""
from homeassistant.config_entries import SOURCE_IMPORT
DOMAIN = "fake_ai"
async def async_setup(hass, config):
    hass.data["fake_ai_last"] = {}
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data={}))
    return True
async def async_setup_entry(hass, entry):
    await hass.config_entries.async_forward_entry_setups(entry, ["ai_task", "stt"])
    return True
async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, ["ai_task", "stt"])

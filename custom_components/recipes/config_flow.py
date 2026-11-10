"""Config flow for Recipes."""

from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AI_TASK_ENTITY,
    CONF_LANGUAGE,
    CONF_NOTIFY_SERVICE,
    CONF_STT_ENTITY,
    CONF_TODO_ENTITY,
    CONF_TRANSCRIBE,
    CONF_WEBHOOK_ID,
    DEFAULT_LANGUAGE,
    DOMAIN,
    LANGUAGES,
)


def _schema(hass, defaults: dict[str, Any]) -> vol.Schema:
    ai_default = defaults.get(CONF_AI_TASK_ENTITY) or next(iter(hass.states.async_entity_ids("ai_task")), None)
    stt_default = defaults.get(CONF_STT_ENTITY) or next(
        (e for e in hass.states.async_entity_ids("stt") if "openai" in e), None
    )
    fields: dict[Any, Any] = {}
    fields[vol.Optional(CONF_AI_TASK_ENTITY, description={"suggested_value": ai_default})] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="ai_task")
    )
    fields[vol.Optional(CONF_STT_ENTITY, description={"suggested_value": stt_default})] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="stt")
    )
    fields[vol.Required(CONF_LANGUAGE, default=defaults.get(CONF_LANGUAGE, DEFAULT_LANGUAGE))] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[selector.SelectOptionDict(value=k, label=v) for k, v in LANGUAGES.items()],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )
    fields[vol.Required(CONF_TRANSCRIBE, default=defaults.get(CONF_TRANSCRIBE, True))] = selector.BooleanSelector()
    todo_default = defaults.get(CONF_TODO_ENTITY) or (
        "todo.shopping_list" if hass.states.get("todo.shopping_list") else None
    )
    fields[vol.Optional(CONF_TODO_ENTITY, description={"suggested_value": todo_default})] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="todo")
    )
    fields[
        vol.Optional(CONF_NOTIFY_SERVICE, description={"suggested_value": defaults.get(CONF_NOTIFY_SERVICE)})
    ] = selector.TextSelector()
    return vol.Schema(fields)


class RecipesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-instance config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle setup."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(
                title="Recipes",
                data={CONF_WEBHOOK_ID: webhook.async_generate_id()},
                options=user_input,
            )
        return self.async_show_form(step_id="user", data_schema=_schema(self.hass, {}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options."""
        return RecipesOptionsFlow()


class RecipesOptionsFlow(OptionsFlow):
    """Change AI entity, language, notifications."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(self.hass, dict(self.config_entry.options)),
            description_placeholders={"webhook": f"/api/webhook/{self.config_entry.data[CONF_WEBHOOK_ID]}"},
        )


__all__ = ["secrets"]

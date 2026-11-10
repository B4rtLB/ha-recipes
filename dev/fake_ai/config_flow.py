from homeassistant.config_entries import ConfigFlow
class FakeFlow(ConfigFlow, domain="fake_ai"):
    async def async_step_import(self, data):
        return self.async_create_entry(title="Fake AI", data={})
    async def async_step_user(self, data=None):
        return self.async_create_entry(title="Fake AI", data={})

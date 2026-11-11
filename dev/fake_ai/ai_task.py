import json, re, uuid
from homeassistant.components.ai_task import AITaskEntity, AITaskEntityFeature, GenDataTaskResult
async def async_setup_entry(hass, entry, add):
    add([FakeAI(hass)])
class FakeAI(AITaskEntity):
    _attr_name = "Fake AI"
    _attr_unique_id = "fake_ai_task"
    _attr_supported_features = AITaskEntityFeature.GENERATE_DATA | AITaskEntityFeature.SUPPORT_ATTACHMENTS
    def __init__(self, hass): self.hass_ = hass
    async def _async_generate_data(self, task, chat_log):
        src = task.instructions.split("SOURCE MATERIAL", 1)[-1]
        self.hass_.data["fake_ai_last"]["prompt"] = task.instructions
        self.hass_.data["fake_ai_last"]["attachments"] = [str(a.path) for a in (task.attachments or [])]
        lean = task.instructions.startswith("Extract ONE recipe")  # the lean prompt: raw strings
        if task.instructions.startswith("A recipe is already parsed"):  # JSON-LD shortcut: tags only
            data = {"tags": ["Main", "Chicken", "#Asian", "Bogus"], "description": "A tagged test dish."}
            return GenDataTaskResult(conversation_id=str(uuid.uuid4()), data=json.dumps(data))
        title = "Test Dish"
        m = re.search(r'"name":\s*"([^"]+)"', src) or re.search(r"RECIPE TEXT:\n(.+)", src)
        if m: title = m.group(1).strip()
        if "NO_RECIPE" in src:
            return GenDataTaskResult(conversation_id=str(uuid.uuid4()), data='{"recipe_found": false, "title": "A dance video"}')
        if lean:
            data = {"recipe_found": True, "title": title, "description": "A quick test dish.", "servings": 4,
              "prep_min": 10, "cook_min": 25,
              "ingredient_groups": [
                {"name": None, "items": ["1.1 lb chicken thighs, boneless", "2-3 cloves garlic", "½ tsp chili flakes", "salt to taste"]},
                {"name": "Sauce", "items": ["200 ml coconut milk", "een snuf zout"]}],
              "steps": ["Fry the chicken for 5 minutes until golden.", "Add the sauce and simmer 10-15 minutes.",
                        "Bake at 400°F for 1 hour 30 minutes.", "Serve with rice."],
              "tags": ["Main", "Chicken", "#Asian", "Bogus"], "source_notes": None}
            return GenDataTaskResult(conversation_id=str(uuid.uuid4()), data=json.dumps(data))
        data = {"recipe_found": True, "title": title, "description": "A quick test dish.", "servings": 4,
          "prep_min": 10, "cook_min": 25, "estimated": False,
          "ingredient_groups": [{"name": None, "items": [
             {"qty": 500, "unit": "g", "name": "chicken thighs", "note": "boneless", "original": "1.1 lb"},
             {"qty": 2, "qty_max": 3, "unit": "clove", "name": "garlic"},
             {"qty": 0.5, "unit": "tsp", "name": "chili flakes"},
             {"qty": None, "unit": None, "name": "salt", "note": "to taste"}]},
             {"name": "Sauce", "items": [{"qty": 200, "unit": "ml", "name": "coconut milk"}]}],
          "steps": [{"text": "Fry the chicken for 5 minutes until golden.", "timers": [{"seconds": 300, "label": "Fry chicken"}]},
                    {"text": "Add the sauce and simmer 10-15 minutes.", "timers": []},
                    {"text": "Serve with rice."}],
          "tags": ["Main", "Chicken", "#Asian", "Bogus"], "source_notes": None}
        return GenDataTaskResult(conversation_id=str(uuid.uuid4()), data="```json\n" + json.dumps(data) + "\n```")

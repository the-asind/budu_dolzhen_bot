import json
from pathlib import Path
from aiogram.fsm.context import FSMContext

# A simple cache for loaded localization files
_LOCALIZATIONS = {}

class Localization:
    def __init__(self, lang_code: str):
        self.lang_code = lang_code
        if lang_code not in _LOCALIZATIONS:
            self._load_lang()

    def _load_lang(self):
        p = Path(__file__).parent / f"{self.lang_code}.json"
        if not p.exists():
            # Fallback to English if the language file doesn't exist
            self.lang_code = "en"
            p = Path(__file__).parent / "en.json"
        
        with open(p, "r", encoding="utf-8") as f:
            _LOCALIZATIONS[self.lang_code] = json.load(f)

    def __getattr__(self, name):
        # Allows accessing localization keys like loc.SETTINGS
        return _LOCALIZATIONS.get(self.lang_code, {}).get(name.upper(), f"_{name.upper()}_")

    @property
    def settings_buttons(self) -> dict:
        return _LOCALIZATIONS.get(self.lang_code, {}).get("settings_buttons", {})

def get_localization(lang_code: str) -> Localization:
    return Localization(lang_code)

async def get_user_language(user_id: int, state: FSMContext) -> str:
    # In a real app, you would fetch this from the database or FSM context.
    # For now, we'll use a placeholder.
    # TODO: Integrate with user repository to get/set user language
    data = await state.get_data()
    return data.get("language", "en") 
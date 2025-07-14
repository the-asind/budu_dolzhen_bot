import json
from pathlib import Path
from aiogram.fsm.context import FSMContext

# simple cache for loaded localization files
_LOCALIZATIONS = {}

class Localization:
    _BUTTON_GROUPS = {
        'debt_buttons': {
            'agree': 'button_agree',
            'decline': 'button_decline',
            'pay': 'button_pay',
            'cancel': 'button_cancel',
            'back': 'button_back',
            'details': 'button_details',
            'recreate': 'button_recreate',
        },
        'payment_buttons': {
            'approve': 'button_approve',
            'reject': 'button_reject',
            'cancel': 'button_cancel',
            'receipt': 'button_receipt',
        },
        'navigation_buttons': {
            'prev': 'button_prev',
            'next': 'button_next',
            'back': 'button_back',
        },
        'debt_filter_buttons': {
            'active': 'button_filter_active',
            'pending': 'button_filter_pending',
            'all': 'button_filter_all',
        },
        'debt_actions': {
            'pay_full': 'button_pay_full',
            'pay_partial': 'button_pay_partial',
            'remind': 'button_remind',
            'view_history': 'button_view_history',
            'back_to_list': 'button_back_to_list',
        },
        'processing_buttons': {
            'cancel': 'button_cancel',
        },
        'summary_buttons': {
            'view_debts': 'button_view_debts',
            'view_credits': 'button_view_credits',
            'create_debt': 'button_create_debt',
            'refresh': 'button_refresh',
        },
        'offset_buttons': {
            'confirm': 'button_offset_confirm',
            'cancel': 'button_offset_cancel',
        },
    }

    def __init__(self, lang_code: str):
        self.lang_code = lang_code
        if lang_code not in _LOCALIZATIONS:
            self._load_lang()

    def _load_lang(self):
        p = Path(__file__).parent / f"{self.lang_code}.json"
        if not p.exists():
            # Fallback to English
            self.lang_code = "en"
            p = Path(__file__).parent / "en.json"

        with open(p, "r", encoding="utf-8") as f:
            _LOCALIZATIONS[self.lang_code] = json.load(f)

    def __getattr__(self, name):
        if name in self._BUTTON_GROUPS:
            loc_data = _LOCALIZATIONS.get(self.lang_code, {})
            result = {}
            for subkey, flat_key in self._BUTTON_GROUPS[name].items():
                if flat_key in loc_data:
                    result[subkey] = loc_data[flat_key]
                else:
                    # Fallback for missing keys
                    result[subkey] = f"_{flat_key.upper()}_"
            return result

        # Allows accessing localization keys like loc.SETTINGS
        return _LOCALIZATIONS.get(self.lang_code, {}).get(name.upper(), f"_{name.upper()}_")

    @property
    def settings_buttons(self) -> dict:
        return _LOCALIZATIONS.get(self.lang_code, {}).get("settings_buttons", {})

def get_localization(lang_code: str) -> Localization:
    return Localization(lang_code)

async def get_user_language(user_id: int, state: FSMContext) -> str:
    # TODO: Integrate with user repository to get/set user language
    data = await state.get_data()
    return data.get("language", "en")

def _(key: str, **kwargs) -> str:
    """Translation shortcut for default (English) locale."""
    loc = Localization("en")
    value = loc.__getattr__(key)
    if kwargs:
        return value.format(**kwargs)
    return value

LANGUAGE_MAP = {
    "en": "en-US-ChristopherNeural",
    "fr": "fr-CA-AntoineNeural",
    "es": "es-ES-AlvaroNeural",
    "de": "de-DE-KillianNeural",
    "it": "it-IT-DiegoNeural",
    "pt": "pt-BR-AntonioNeural",
    "nl": "nl-NL-MaartenNeural",
    "pl": "pl-PL-MarekNeural",
    "ru": "ru-RU-DmitryNeural",
    "ja": "ja-JP-KeitaNeural",
    "ko": "ko-KR-InJoonNeural",
    "zh": "zh-CN-YunxiNeural",
    "ar": "ar-SA-HamedNeural",
    "tr": "tr-TR-AhmetNeural",
    "sv": "sv-SE-MattiasNeural",
    "da": "da-DK-JeppeNeural",
    "fi": "fi-FI-HarriNeural",
    "nb": "nb-NO-FinnNeural",
    "cs": "cs-CZ-AntoninNeural",
    "hu": "hu-HU-TamasNeural",
    "ro": "ro-RO-EmilNeural",
    "th": "th-TH-NiwatNeural",
    "vi": "vi-VN-NamMinhNeural",
}

LANGUAGE_NAMES = {
    "en": "English",
    "fr": "Francais",
    "es": "Espanol",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Portugues",
    "nl": "Nederlands",
    "pl": "Polski",
    "ru": "Russkiy",
    "ja": "Nihongo",
    "ko": "Hangug-eo",
    "zh": "Zhongwen",
    "ar": "Alarabia",
    "tr": "Turkce",
    "sv": "Svenska",
    "da": "Dansk",
    "fi": "Suomi",
    "nb": "Norsk",
    "cs": "Cestina",
    "hu": "Magyar",
    "ro": "Romana",
    "th": "Thai",
    "vi": "Tieng Viet",
}

SUPPORTED_LANGUAGES = sorted(LANGUAGE_NAMES.keys())


class Translator:
    def __init__(self, target_language: str = "en"):
        self.target_language = target_language
        self._translator = None
        if target_language != "en":
            try:
                from deep_translator import GoogleTranslator
                self._translator = GoogleTranslator(source="auto", target=target_language)
            except ImportError:
                print("[Translator] deep-translator not installed. Translations disabled.")
            except Exception as e:
                print(f"[Translator] Init error: {e}")

    def translate(self, text: str) -> str:
        if self.target_language == "en" or not text or self._translator is None:
            return text
        try:
            return self._translator.translate(text)
        except Exception as e:
            print(f"[Translator] Error translating '{text[:40]}...': {e}")
            return text

    def translate_list(self, texts: list[str]) -> list[str]:
        return [self.translate(t) for t in texts]

    def get_tts_voice(self) -> str:
        return LANGUAGE_MAP.get(self.target_language, "en-US-ChristopherNeural")

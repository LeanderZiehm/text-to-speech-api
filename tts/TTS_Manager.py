from Espeak_TTSGenerator import ESpeakTTSGenerator

# enum
from enum import Enum

# enum for TTS options


# select TTS
class TTSManager:
    def __init__(self):
        self.tts_generator = None
        self.selected_tts = None

    class TTSOptions(Enum):
        ESPEAK = "espeak"
        GOOGLE = "google"
        COQUI = "coqui"

    def select_tts(self, tts_option: TTSOptions):
        if tts_option == self.TTSOptions.ESPEAK:
            self.tts_generator = ESpeakTTSGenerator()
        elif tts_option == self.TTSOptions.GOOGLE:
            # self.tts_generator = GoogleTTSGenerator()
            pass
        elif tts_option == self.TTSOptions.COQUI:
            # self.tts_generator = CoquiTTSGenerator()
            pass
        else:
            raise ValueError("Invalid TTS option selected.")
        self.selected_tts = tts_option
        print(f"Selected TTS: {self.selected_tts.value}")

    def get_tts_generator(self):
        if self.tts_generator is None:
            raise ValueError("No TTS generator selected.")
        return self.tts_generator

    def generate_tts(self, text: str, output_file: str):
        if self.tts_generator is None:
            raise ValueError("No TTS generator selected.")
        self.tts_generator.generate_tts(text, output_file)

    def get_output_format(self):
        if self.tts_generator is None:
            raise ValueError("No TTS generator selected.")
        return self.tts_generator.get_output_format()

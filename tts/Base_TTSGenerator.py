from abc import ABC, abstractmethod


class TTSGenerator(ABC):
    @abstractmethod
    def get_output_format(self) -> str:
        """Return the audio file format (e.g., 'wav', 'mp3')."""
        pass

    @abstractmethod
    def generate_tts(self, text: str, output_file: str) -> None:
        """Generate TTS audio from text and write it to output_file."""
        pass

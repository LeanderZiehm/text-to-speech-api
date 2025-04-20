import subprocess
from Base_TTSGenerator import TTSGenerator


class ESpeakTTSGenerator(TTSGenerator):
    def get_output_format(self) -> str:
        return "wav"

    def generate_tts(self, text: str, output_file: str) -> None:
        try:
            subprocess.run(
                ["espeak", "-w", output_file, text],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"eSpeak error: {e.stderr}")

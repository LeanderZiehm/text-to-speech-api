# app.py
import os
import threading
import subprocess
from flask import Flask, request, jsonify, send_file, render_template
from datetime import datetime
import shutil
import hashlib
from pydub import AudioSegment
import re

from tts.TTS_Manager import TTSManager

app = Flask(__name__)

# Configuration
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# Create required directories if they don't exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# Dictionary to store job status
jobs = {}


file_format = "mp3"
# file_format = "wav"

ttsManager = TTSManager()


def getSlicedText(text, charsToKeep):
    return text.strip()[:charsToKeep]


def sanitize_filename(input_str):
    cleaned = input_str.replace("\n", "").replace("\r", "")
    safe_str = re.sub(r"[^\w\-_.]", "_", cleaned)
    return safe_str


class AudioJob:
    def __init__(self, text):
        self.job_id = hashlib.sha256(text.encode()).hexdigest()
        self.text = text
        self.status = "processing"
        self.created_at = datetime.now()
        sliced_text = getSlicedText(text, 20)
        file_name_front = sanitize_filename(sliced_text)
        file_name = f"{file_name_front}.{file_format}"
        self.output_file_name = f"{file_name_front}_tts.{file_format}"
        self.output_file_path = os.path.join(RESULT_DIR, self.output_file_name)
        self.error = None
        self.progress = 0  # Track progress from 0-100

    def process(self):
        try:
            # Create a temp directory for this job's chunks
            job_temp_dir = os.path.join(TEMP_DIR, self.job_id)
            os.makedirs(job_temp_dir, exist_ok=True)

            # Split text into manageable chunks (roughly by sentences)
            chunks = self._split_text(self.text)
            total_chunks = len(chunks)

            # Update progress to 10% after text splitting
            self.progress = 10

            chunk_files = []
            for i, chunk in enumerate(chunks):

                ttsManager.select_tts(ttsManager.TTSOptions.ESPEAK)

                # Generate chunk files using the selected TTS
                chunk_file = os.path.join(
                    job_temp_dir, f"chunk_{i}.{ttsManager.get_output_format()}"
                )
                ttsManager.generate_tts(chunk, chunk_file)
                chunk_files.append(chunk_file)

                # Update progress (allocate 70% of progress to speech generation)
                self.progress = 10 + int(70 * (i + 1) / total_chunks)

            # Merge audio files using ffmpeg
            self.progress = 80  # 80% progress before merging

            if file_format == "mp3":

                self._merge_audio_files_pydub_wav_to_mp3(
                    chunk_files, self.output_file_path
                )

                # self._merge_audio_files_ffmpeg_wav_to_mp3(chunk_files, self.output_file_path)

            else:
                self._merge_audio_files_ffmpeg_wav_to_wav(
                    chunk_files, self.output_file_path
                )
            self.progress = 95  # 95% after merging

            # Clean up temp files for this job
            shutil.rmtree(job_temp_dir)

            # Update job status
            self.status = "completed"
            self.progress = 100  # 100% when completed
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            print(f"Error processing job {self.job_id}: {e}")

    def _split_text(self, text, max_chars=500):
        # Split text into sentences and group them into chunks
        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) < max_chars:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence + ". "

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _merge_audio_files_pydub_wav_to_mp3(
        self, input_files, output_file, bitrate="192k"
    ):
        """
        Merge a list of WAV files into a single MP3 using pydub.
        """
        if not input_files:
            raise Exception("No audio chunks to merge")

        # Start with an empty AudioSegment
        combined = AudioSegment.empty()
        for wav in input_files:
            combined += AudioSegment.from_wav(wav)

        # Export as MP3
        try:
            combined.export(output_file, format="mp3", bitrate=bitrate)
        except Exception as e:
            raise Exception(f"pydub export error: {e}")

    def _merge_audio_files_ffmpeg_wav_to_mp3(
        self, input_files, output_file, bitrate="192k"
    ):
        """
        Merge a list of WAV files into a single MP3 using ffmpeg concat demuxer.
        """
        if not input_files:
            raise Exception("No audio chunks to merge")

        # Create a ffmpeg "list" file
        list_file = os.path.join(TEMP_DIR, f"{self.job_id}_mp3_list.txt")
        with open(list_file, "w") as f:
            for wav in input_files:
                # ffmpeg requires escaped paths if they contain special chars
                f.write(f"file '{wav}'\n")

        # Build ffmpeg command:
        #  - concat demuxer reads the list, then re-encodes to MP3
        cmd = [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            output_file,
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            # include stderr for diagnostics
            raise Exception(f"FFmpeg error: {e.stderr}")
        finally:
            # Clean up the temporary list file
            if os.path.exists(list_file):
                os.remove(list_file)

    def _merge_audio_files_ffmpeg_wav_to_wav(self, input_files, output_file):
        # Use ffmpeg to concatenate audio files
        if not input_files:
            raise Exception("No audio chunks to merge")

        # Create a file list for ffmpeg
        list_file = os.path.join(TEMP_DIR, f"{self.job_id}_list.txt")
        with open(list_file, "w") as f:
            for file in input_files:
                f.write(f"file '{file}'\n")

        # Run ffmpeg to concatenate files
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    list_file,
                    "-c",
                    "copy",
                    output_file,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            # Remove the temporary list file
            os.remove(list_file)
        except subprocess.CalledProcessError as e:
            raise Exception(f"FFmpeg error: {e.stderr}")


def start_job(text):
    job = AudioJob(text)
    jobs[job.job_id] = job

    # Start processing in background thread
    thread = threading.Thread(target=job.process)
    thread.daemon = True
    thread.start()

    return job.job_id


@app.route("/", methods=["GET"])
def index():
    """Serve the frontend HTML page."""
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate_audio():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    if "text" not in data or not data["text"].strip():
        return jsonify({"error": "Text is required"}), 400

    job_id = start_job(data["text"])

    return jsonify({"job_id": job_id, "status": "processing"})


@app.route("/status/<job_id>", methods=["GET"])
def check_status(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404

    job = jobs[job_id]

    response = {
        "job_id": job_id,
        "status": job.status,
        "created_at": job.created_at.isoformat(),
        "progress": job.progress,  # Include progress in the response
    }

    if job.status == "failed" and job.error:
        response["error"] = job.error

    return jsonify(response)


@app.route("/result/<job_id>", methods=["GET"])
def get_result(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404

    job = jobs[job_id]

    if job.status == "processing":
        return jsonify(
            {
                "job_id": job_id,
                "status": "processing",
                "message": "Audio generation is still in progress",
            }
        )

    if job.status == "failed":
        return (
            jsonify(
                {
                    "job_id": job_id,
                    "status": "failed",
                    "error": job.error or "Unknown error occurred",
                }
            ),
            500,
        )

    # If completed, return the audio file
    if os.path.exists(job.output_file_path):
        return send_file(
            job.output_file_path,
            mimetype="audio/{file_format}",
            as_attachment=True,
            download_name=job.output_file_name,
        )
    else:
        return jsonify({"error": "Audio file not found"}), 404


if __name__ == "__main__":

    app.run(debug=True, port=5001)

# app.py
import os
import uuid
import time
import threading
import subprocess
import json
from flask import Flask, request, jsonify, send_file
from datetime import datetime, timedelta
import shutil

app = Flask(__name__)

# Configuration
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
MAX_FILE_AGE_HOURS = 1
CLEANUP_INTERVAL_SECONDS = 3600  # Run cleanup every hour

# Create required directories if they don't exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# Dictionary to store job status
jobs = {}


class AudioJob:
    def __init__(self, text):
        self.job_id = str(uuid.uuid4())
        self.text = text
        self.status = "processing"
        self.created_at = datetime.now()
        self.output_file = os.path.join(RESULT_DIR, f"{self.job_id}.wav")
        self.error = None

    def process(self):
        try:
            # Create a temp directory for this job's chunks
            job_temp_dir = os.path.join(TEMP_DIR, self.job_id)
            os.makedirs(job_temp_dir, exist_ok=True)
            
            # Split text into manageable chunks (roughly by sentences)
            chunks = self._split_text(self.text)
            
            chunk_files = []
            for i, chunk in enumerate(chunks):
                # Convert each chunk to audio using eSpeak
                chunk_file = os.path.join(job_temp_dir, f"chunk_{i}.wav")
                self._text_to_speech(chunk, chunk_file)
                chunk_files.append(chunk_file)
            
            # Merge audio files using ffmpeg
            self._merge_audio_files(chunk_files, self.output_file)
            
            # Clean up temp files for this job
            shutil.rmtree(job_temp_dir)
            
            # Update job status
            self.status = "completed"
        except Exception as e:
            self.status = "failed"
            self.error = str(e)
            print(f"Error processing job {self.job_id}: {e}")

    def _split_text(self, text, max_chars=500):
        # Split text into sentences and group them into chunks
        sentences = [s.strip() for s in text.replace('\n', ' ').split('.') if s.strip()]
        
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

    def _text_to_speech(self, text, output_file):
        # Use eSpeak to convert text to speech
        # We'll use subprocess to call the espeak command
        try:
            subprocess.run([
                'espeak',
                '-w', output_file,
                text
            ], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"eSpeak error: {e.stderr}")

    def _merge_audio_files(self, input_files, output_file):
        # Use ffmpeg to concatenate audio files
        if not input_files:
            raise Exception("No audio chunks to merge")
        
        # Create a file list for ffmpeg
        list_file = os.path.join(TEMP_DIR, f"{self.job_id}_list.txt")
        with open(list_file, 'w') as f:
            for file in input_files:
                f.write(f"file '{file}'\n")
        
        # Run ffmpeg to concatenate files
        try:
            subprocess.run([
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                output_file
            ], check=True, capture_output=True, text=True)
            
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


def cleanup_old_files():
    """Periodically clean up old result files"""
    while True:
        try:
            now = datetime.now()
            # Clean up old jobs from memory
            expired_jobs = [job_id for job_id, job in jobs.items() 
                          if now - job.created_at > timedelta(hours=MAX_FILE_AGE_HOURS)]
            
            for job_id in expired_jobs:
                if job_id in jobs:
                    del jobs[job_id]
            
            # Clean up old files from disk
            for dir_path in [TEMP_DIR, RESULT_DIR]:
                for filename in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, filename)
                    if os.path.isfile(file_path):
                        file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if now - file_mod_time > timedelta(hours=MAX_FILE_AGE_HOURS):
                            os.remove(file_path)
        except Exception as e:
            print(f"Error during cleanup: {e}")
        
        time.sleep(CLEANUP_INTERVAL_SECONDS)


# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files)
cleanup_thread.daemon = True
cleanup_thread.start()


@app.route('/generate', methods=['POST'])
def generate_audio():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.get_json()
    if 'text' not in data or not data['text'].strip():
        return jsonify({"error": "Text is required"}), 400
    
    job_id = start_job(data['text'])
    
    return jsonify({
        "job_id": job_id,
        "status": "processing"
    })


@app.route('/status/<job_id>', methods=['GET'])
def check_status(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    
    response = {
        "job_id": job_id,
        "status": job.status,
        "created_at": job.created_at.isoformat()
    }
    
    if job.status == "failed" and job.error:
        response["error"] = job.error
    
    return jsonify(response)


@app.route('/result/<job_id>', methods=['GET'])
def get_result(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    
    if job.status == "processing":
        return jsonify({
            "job_id": job_id,
            "status": "processing",
            "message": "Audio generation is still in progress"
        })
    
    if job.status == "failed":
        return jsonify({
            "job_id": job_id,
            "status": "failed",
            "error": job.error or "Unknown error occurred"
        }), 500
    
    # If completed, return the audio file
    if os.path.exists(job.output_file):
        return send_file(
            job.output_file,
            mimetype='audio/wav',
            as_attachment=True,
            download_name=f"text_to_speech_{job_id}.wav"
        )
    else:
        return jsonify({
            "error": "Audio file not found"
        }), 404


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

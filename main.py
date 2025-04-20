# app.py
import os
import threading
import subprocess
from flask import Flask, request, jsonify, send_file, render_template_string
from datetime import datetime
import shutil
import hashlib

app = Flask(__name__)

# Configuration
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
RESULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# Create required directories if they don't exist
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# Dictionary to store job status
jobs = {}


class AudioJob:
    def __init__(self, text):
        self.job_id = hashlib.sha256(text.encode()).hexdigest()
        self.text = text
        self.status = "processing"
        self.created_at = datetime.now()
        self.output_file = os.path.join(RESULT_DIR, f"{self.job_id}.wav")
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
                # Convert each chunk to audio using eSpeak
                chunk_file = os.path.join(job_temp_dir, f"chunk_{i}.wav")
                self._text_to_speech(chunk, chunk_file)
                chunk_files.append(chunk_file)

                # Update progress (allocate 70% of progress to speech generation)
                self.progress = 10 + int(70 * (i + 1) / total_chunks)

            # Merge audio files using ffmpeg
            self.progress = 80  # 80% progress before merging
            self._merge_audio_files(chunk_files, self.output_file)
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

    def _text_to_speech(self, text, output_file):
        # Use eSpeak to convert text to speech
        # We'll use subprocess to call the espeak command
        try:
            subprocess.run(
                ["espeak", "-w", output_file, text],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"eSpeak error: {e.stderr}")

    def _merge_audio_files(self, input_files, output_file):
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


# HTML template for the frontend
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Text to Speech Converter</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }
        h1 {
            text-align: center;
            color: #333;
        }
        .container {
            background-color: #f9f9f9;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        #textInput {
            width: 100%;
            min-height: 150px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            margin-bottom: 15px;
            box-sizing: border-box;
        }
        button {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        button:disabled {
            background-color: #cccccc;
            cursor: not-allowed;
        }
        .progress-container {
            margin-top: 20px;
            display: none;
        }
        progress {
            width: 100%;
            height: 20px;
        }
        .status {
            margin-top: 10px;
            text-align: center;
        }
        #downloadContainer {
            margin-top: 20px;
            text-align: center;
            display: none;
        }
        #errorMessage {
            color: red;
            margin-top: 10px;
            display: none;
        }
    </style>
</head>
<body>
    <h1>Text to Speech Converter</h1>
    
    <div class="container">
        <div>
            <textarea id="textInput" placeholder="Enter your text here..."></textarea>
        </div>
        
        <div>
            <button id="submitBtn">Convert to Speech</button>
        </div>
        
        <div class="progress-container" id="progressContainer">
            <h3>Processing your audio...</h3>
            <progress id="progressBar" value="0" max="100"></progress>
            <div class="status" id="statusText">Starting conversion...</div>
        </div>
        
        <div id="errorMessage"></div>
        
        <div id="downloadContainer">
            <h3>Your audio is ready!</h3>
            <button id="downloadBtn">Download Audio</button>
        </div>
    </div>

    <script>
        let jobId = null;
        let pollingInterval = null;
        
        document.getElementById('submitBtn').addEventListener('click', async function() {
            const text = document.getElementById('textInput').value.trim();
            
            if (!text) {
                alert('Please enter some text to convert');
                return;
            }
            
            // Disable button and show progress
            this.disabled = true;
            document.getElementById('progressContainer').style.display = 'block';
            document.getElementById('downloadContainer').style.display = 'none';
            document.getElementById('errorMessage').style.display = 'none';
            
            try {
                // Submit text for conversion
                const response = await fetch('/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ text: text }),
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    jobId = data.job_id;
                    
                    // Start polling for status updates
                    startPolling();
                } else {
                    showError(data.error || 'Failed to submit conversion request');
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('progressContainer').style.display = 'none';
                }
            } catch (error) {
                showError('Error submitting request: ' + error.message);
                document.getElementById('submitBtn').disabled = false;
                document.getElementById('progressContainer').style.display = 'none';
            }
        });
        
        document.getElementById('downloadBtn').addEventListener('click', function() {
            if (jobId) {
                // Trigger download
                window.location.href = '/result/' + jobId;
            }
        });
        
        function startPolling() {
            // Poll every second
            pollingInterval = setInterval(checkStatus, 1000);
        }
        
        async function checkStatus() {
            try {
                const response = await fetch('/status/' + jobId);
                const data = await response.json();
                
                if (response.ok) {
                    updateProgress(data);
                    
                    if (data.status === 'completed') {
                        // Job is complete
                        clearInterval(pollingInterval);
                        showDownloadButton();
                        // Auto download
                        window.location.href = '/result/' + jobId;
                    } else if (data.status === 'failed') {
                        // Job failed
                        clearInterval(pollingInterval);
                        showError(data.error || 'Conversion failed');
                        document.getElementById('submitBtn').disabled = false;
                        document.getElementById('progressContainer').style.display = 'none';
                    }
                } else {
                    showError(data.error || 'Failed to check status');
                    clearInterval(pollingInterval);
                    document.getElementById('submitBtn').disabled = false;
                    document.getElementById('progressContainer').style.display = 'none';
                }
            } catch (error) {
                showError('Error checking status: ' + error.message);
                clearInterval(pollingInterval);
                document.getElementById('submitBtn').disabled = false;
                document.getElementById('progressContainer').style.display = 'none';
            }
        }
        
        function updateProgress(data) {
            // Update progress bar and status text
            const progressBar = document.getElementById('progressBar');
            const statusText = document.getElementById('statusText');
            
            if (data.progress !== undefined) {
                progressBar.value = data.progress;
            }
            
            if (data.status === 'processing') {
                statusText.textContent = `Processing: ${data.progress || 0}%`;
            } else if (data.status === 'completed') {
                progressBar.value = 100;
                statusText.textContent = 'Processing complete!';
            }
        }
        
        function showDownloadButton() {
            document.getElementById('progressContainer').style.display = 'none';
            document.getElementById('downloadContainer').style.display = 'block';
            document.getElementById('submitBtn').disabled = false;
        }
        
        function showError(message) {
            const errorElement = document.getElementById('errorMessage');
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }
    </script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    """Serve the frontend HTML page."""
    return render_template_string(HTML_TEMPLATE)


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
    if os.path.exists(job.output_file):
        return send_file(
            job.output_file,
            mimetype="audio/wav",
            as_attachment=True,
            download_name=f"text_to_speech_{job_id}.wav",
        )
    else:
        return jsonify({"error": "Audio file not found"}), 404


if __name__ == "__main__":

    app.run(debug=True, host="0.0.0.0", port=5000)

# Text-to-Audio API Setup Instructions

## Prerequisites

Before running the API, you need to install the following dependencies:

1. **Python 3.7+**
2. **eSpeak** - Text-to-speech synthesizer
3. **FFmpeg** - For audio processing and merging

## Installation Guide

### 1. Install System Dependencies

#### On Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y espeak ffmpeg
```

#### On Windows:
- Download and install eSpeak from: http://espeak.sourceforge.net/download.html
- Download and install FFmpeg from: https://ffmpeg.org/download.html
- Add both to your system PATH

### 2. Python Dependencies

Create a virtual environment and install required packages:

```bash
# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install requirements
pip install flask
```

### 3. Project Setup

1. Create the project structure:
```
text-to-audio-api/
├── app.py
├── temp/    # Will be created automatically
└── results/ # Will be created automatically
```

2. Place the `app.py` file in the project root directory

## Running the API

```bash
# Navigate to project directory
cd text-to-audio-api

# Activate virtual environment if not already activated
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Run the Flask application
python app.py
```

The API will start running on http://localhost:5000

## API Endpoints

1. **Generate Audio**
   - URL: `/generate`
   - Method: POST
   - Body: `{"text": "Your text to convert to speech"}`
   - Response: `{"job_id": "unique-id", "status": "processing"}`

2. **Check Job Status**
   - URL: `/status/<job_id>`
   - Method: GET
   - Response: `{"job_id": "unique-id", "status": "processing|completed|failed", "created_at": "timestamp"}`

3. **Get Result**
   - URL: `/result/<job_id>`
   - Method: GET
   - Response: Audio file download or status message if not ready

## Testing the API

You can test the API using curl commands:

```bash
# Submit a text for conversion
curl -X POST -H "Content-Type: application/json" -d '{"text":"Hello world, this is a test of the text to speech API using eSpeak."}' http://localhost:5000/generate

# Check job status (replace JOB_ID with the actual ID from the previous response)
curl http://localhost:5000/status/JOB_ID

# Download result (when status is "completed")
curl -OJ http://localhost:5000/result/JOB_ID
```

## Important Notes

- Audio files and jobs are automatically cleaned up after 1 hour
- The system uses eSpeak for TTS conversion and FFmpeg for audio processing
- For production use, consider adding authentication and rate limiting

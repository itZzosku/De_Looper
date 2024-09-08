import subprocess
import os
import json

# Twitch configuration
Twitch_Stream_Key = "live_1138107151_TllNxIhHwf0DI62aRS60XCA94YWrEN"
Twitch_URL = f"rtmp://live.twitch.tv/app/{Twitch_Stream_Key}"

# Define the path to playlist.json and progress.json (in the same folder as main.py)
script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory where the script is located
playlist_json = os.path.join(script_dir, "playlist.json")
progress_json = os.path.join(script_dir, "progress.json")

# Track running subprocesses for graceful shutdown
stream_proc = None
normalize_proc = None


# Function to read playlist from the JSON file with UTF-8 encoding (for special characters)
def get_media_files_from_playlist(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:  # Ensure UTF-8 encoding
        data = json.load(f)
    return data.get("playlist", [])


# Function to save the last played id to progress.json
def save_progress(last_id):
    with open(progress_json, 'w', encoding='utf-8') as f:
        json.dump({"last_played_id": last_id}, f)


# Function to load the last played id from progress.json
def load_progress():
    if os.path.exists(progress_json):
        with open(progress_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("last_played_id", None)  # Return None if no id found
    return None


# Graceful shutdown function
def graceful_shutdown(signum, frame):
    global stream_proc, normalize_proc
    print("Shutting down...")
    if normalize_proc:
        normalize_proc.terminate()  # Stop the first FFmpeg process
    if stream_proc:
        stream_proc.stdin.close()  # Close the pipe to stop the streaming process
        stream_proc.terminate()  # Terminate the streaming FFmpeg process


# Register the shutdown handler
import signal

signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)


# Function to normalize and pipe the video to the streaming FFmpeg instance
def normalize_and_stream(media_files, last_played_id=None):
    global stream_proc, normalize_proc

    # FFmpeg command to stream to Twitch (this instance is always running)
    stream_command = [
        "ffmpeg",
        "-loglevel", "error",  # Only show errors
        "-re",  # Ensure real-time streaming
        "-i", "pipe:0",  # Read from stdin (pipe from normalization FFmpeg process)
        "-c:v", "libx264",  # Encode video to H.264
        "-c:a", "aac",  # Encode audio to AAC
        "-ar", "44100",  # Audio sample rate
        "-f", "flv",  # Output format for Twitch
        Twitch_URL  # Streaming URL for Twitch
    ]

    # Start the stream subprocess and keep it running
    print("Starting streaming process...")
    stream_proc = subprocess.Popen(stream_command, stdin=subprocess.PIPE)

    # Find the position of the last played video by id
    start_index = 0
    if last_played_id is not None:
        for i, media in enumerate(media_files):
            if media['id'] == last_played_id:
                start_index = i + 1  # Start from the next video after the last played one
                break

    # Iterate through media files and normalize/pipe each clip starting from the last played id
    for idx, media in enumerate(media_files[start_index:], start=start_index):
        media_file = media.get('file_path')
        media_id = media.get('id')

        if not os.path.exists(media_file):
            print(f"File {media_file} does not exist!")
            continue

        # FFmpeg command to normalize the video and pipe it to stdout
        normalize_command = [
            "ffmpeg",
            "-loglevel", "error",  # Only show errors
            "-i", media_file,  # Input video file
            "-s", "1280x720",  # Scale video to 720p
            "-c:v", "mpeg2video",  # Video codec
            "-b:v", "50M",  # Video bitrate
            "-c:a", "s302m",  # Audio codec
            "-strict", "-2",  # Enable non-standard codecs
            "-ar", "48k",  # Audio sample rate
            "-f", "mpegts",  # Output format (MPEG-TS)
            "-"  # Pipe output to stdout
        ]

        print(f"Normalizing and streaming: {media_file}")

        # Start the normalization process and pipe its output to the streaming process
        normalize_proc = subprocess.Popen(normalize_command, stdout=subprocess.PIPE)
        while True:
            data = normalize_proc.stdout.read(65536)
            if not data:
                break
            stream_proc.stdin.write(data)
        normalize_proc.wait()

        # Save progress after each clip is streamed (using the id now)
        save_progress(media_id)
        print(f"Progress saved. Last played video id: {media_id}.")

    # Close the stream after all videos are processed
    stream_proc.stdin.close()
    stream_proc.wait()


# Main function to run the whole process
def main():
    # Get media files from the playlist JSON
    print(f"Using playlist: {playlist_json}")
    media_files = get_media_files_from_playlist(playlist_json)

    if not media_files:
        print("No media files found in playlist!")
        return

    # Load the last played id from progress.json
    last_played_id = load_progress()
    if last_played_id:
        print(f"Resuming from video id: {last_played_id}")
    else:
        print("Starting from the first video.")

    # Normalize and stream the clips starting from the last played id
    normalize_and_stream(media_files, last_played_id=last_played_id)


if __name__ == "__main__":
    main()

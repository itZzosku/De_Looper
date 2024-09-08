import subprocess
import os
import json
import signal
import threading

# Load Twitch configuration from config.json (make sure this file is ignored by git)
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_file, 'r', encoding='utf-8') as f:
    config_data = json.load(f)
    Twitch_Stream_Key = config_data.get("Twitch_Stream_Key")

if not os.path.exists(config_file):
    raise FileNotFoundError("Configuration file 'config.json' is missing. Please create it and add your Twitch Stream Key.")


Twitch_URL = f"rtmp://live.twitch.tv/app/{Twitch_Stream_Key}"

# Define the path to playlist.json and progress.json (in the same folder as main.py)
script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory where the script is located
playlist_json = os.path.join(script_dir, "playlist.json")
progress_json = os.path.join(script_dir, "progress.json")

# Global variables to handle skip functionality
stream_proc = None
normalize_proc = None
skip_next = False
skip_to_id = None


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


# Function to handle the skip command
def handle_skip_command():
    global skip_next, skip_to_id
    while True:
        command = input()  # Listen for command input
        command_parts = command.strip().split()

        if command_parts[0].lower() == 'skip':
            skip_next = True  # Set the skip flag to True
            print("Skipping to the next video...")

        elif command_parts[0].lower() == 'skiptoid' and len(command_parts) > 1:
            try:
                skip_to_id = int(command_parts[1])  # Set the skip_to_id to the entered ID
                print(f"Skipping to video with ID: {skip_to_id}")
            except ValueError:
                print("Invalid ID entered. Please enter a valid numeric ID.")


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
signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)


# Function to normalize and pipe the video to the streaming FFmpeg instance
def normalize_and_stream(media_files, last_played_id=None):
    global stream_proc, normalize_proc, skip_next, skip_to_id

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
    while True:  # Infinite loop to restart the playlist from the beginning
        idx = start_index
        while idx < len(media_files):
            media = media_files[idx]
            media_file = media.get('file_path')
            media_id = media.get('id')

            # Check if skip_to_id was set and jump to the requested id
            if skip_to_id is not None:
                # Look for the media with the matching id
                media = next((m for m in media_files if m['id'] == skip_to_id), None)
                if media:
                    idx = media_files.index(media)  # Set the index to the found media
                    save_progress(media['id'])  # Save progress after jumping to the ID
                    print(f"Progress saved. Last played video id: {media['id']}.")
                    skip_to_id = None  # Reset the skip_to_id flag
                else:
                    print(f"Video with ID: {skip_to_id} not found.")
                    skip_to_id = None
                continue

            if not os.path.exists(media_file):
                print(f"File {media_file} does not exist!")
                idx += 1
                continue

            # FFmpeg command to normalize the video and pipe it to stdout (H.264 and AAC)
            normalize_command = [
                "ffmpeg",
                "-loglevel", "error",  # Only show errors
                "-i", media_file,  # Input video file
                "-s", "1280x720",  # Scale video to 720p
                "-c:v", "libx264",  # Video codec H.264
                "-b:v", "2500k",  # Video bitrate
                "-g", "60",  # Force a keyframe every 60 frames (2 seconds at 30fps)
                "-c:a", "aac",  # Audio codec AAC
                "-ar", "44100",  # Audio sample rate
                "-f", "mpegts",  # Output format (MPEG-TS)
                "-"  # Pipe output to stdout
            ]

            print(f"Normalizing and streaming: {media_file}")

            # Start the normalization process and pipe its output to the streaming process
            normalize_proc = subprocess.Popen(normalize_command, stdout=subprocess.PIPE)

            while True:
                data = normalize_proc.stdout.read(65536)
                if not data or skip_next or skip_to_id is not None:  # If no data or skip is triggered, break the loop
                    if skip_next or skip_to_id is not None:
                        normalize_proc.terminate()  # Stop the current normalization process
                        stream_proc.stdin.flush()  # Flush remaining data before starting next clip
                        skip_next = False  # Reset skip flag for the next video
                    break
                stream_proc.stdin.write(data)
            normalize_proc.wait()

            # Save progress after each clip is streamed (using the id now)
            save_progress(media_id)
            print(f"Progress saved. Last played video id: {media_id}.")
            idx += 1

        # If the playlist ends, start from the beginning again
        print("Reached the end of the playlist. Restarting from the beginning.")
        start_index = 0


# Main function to run the whole process
def main():
    # Start a thread to listen for the "skip" and "skiptoid" commands
    skip_thread = threading.Thread(target=handle_skip_command, daemon=True)
    skip_thread.start()

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

import subprocess
import os
import json
import signal
import sys  # To handle command-line arguments
import time  # For introducing small delays to improve transitions

# Global variables for processes
stream_proc = None
normalize_proc = None  # Ensure both are initialized at the module level

# Twitch configuration
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_file, 'r', encoding='utf-8') as f:
    config_data = json.load(f)
    Twitch_Stream_Key = config_data.get("Twitch_Stream_Key")

Twitch_URL = f"rtmp://live.twitch.tv/app/{Twitch_Stream_Key}"

# Define the path to playlist.json and progress.json (in the same folder as main.py)
script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory where the script is located
playlist_json = os.path.join(script_dir, "playlist.json")
progress_json = os.path.join(script_dir, "progress.json")

# Global variable to hold the stream command
stream_command = [
    "ffmpeg",
    "-loglevel", "error",  # Only show errors
    "-re",  # Ensure real-time streaming
    "-i", "pipe:0",  # Read from stdin (pipe from normalization FFmpeg process or file stream)
    "-c:v", "libx264",  # Encode video to H.264
    "-c:a", "aac",  # Encode audio to AAC
    "-ar", "44100",  # Audio sample rate
    "-b:v", "2300k",  # Set video bitrate to 2300k to match normalization
    "-maxrate", "2300k",  # Max bitrate set to 2300k to align with clip encoding
    "-g", "60",  # Keyframe interval (for 30fps, keyframe every 2 seconds)
    "-flvflags", "no_duration_filesize",  # Helps avoid certain FLV-specific issues
    "-f", "flv",  # Output format for Twitch
    Twitch_URL  # Streaming URL for Twitch
]

# Function to play a 3-second black screen transition
def play_transition():
    # Play a 3-second black screen transition
    print("Playing 3-second black screen transition between clips...")

    # FFmpeg command to generate a black screen (3 seconds, 1280x720 resolution)
    ffmpeg_command = [
        "ffmpeg",
        "-f", "lavfi",  # Use lavfi to generate input
        "-loglevel", "error",  # Only show errors
        "-i", "color=c=black:s=1280x720:r=30:d=3",  # Black screen, 1280x720 resolution, 3 seconds long
        "-c:v", "libx264",  # Encode video to H.264
        "-t", "3",  # Duration of the black screen (3 seconds)
        "-f", "mpegts",  # Output format for Twitch
        "-"  # Pipe output to stdout
    ]

    # Play the black screen and pipe it into the stream
    transition_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE)

    while True:
        data = transition_proc.stdout.read(65536)
        if not data:  # Break when done playing the transition
            break
        stream_proc.stdin.write(data)  # Pipe black screen data to the stream

    transition_proc.wait()


# Function to read playlist from the JSON file with UTF-8 encoding (for special characters)
def get_media_files_from_playlist(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
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

    # Check and terminate the normalization process, if it exists
    if normalize_proc and normalize_proc.poll() is None:  # Check if the process is running
        normalize_proc.terminate()  # Stop the first FFmpeg process

    # Check and terminate the stream process, if it exists
    if stream_proc and stream_proc.poll() is None:  # Check if the process is running
        stream_proc.stdin.close()  # Close the pipe to stop the streaming process
        stream_proc.terminate()  # Terminate the streaming FFmpeg process


# Register the shutdown handler
signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)


# Function to pipe media to the streaming FFmpeg instance
def pipe_to_stream(media_file, is_preprocessed):
    global stream_proc, normalize_proc

    if is_preprocessed:
        # Pipe preprocessed file to the streaming FFmpeg instance without re-encoding
        print(f"Streaming preprocessed file (no re-encoding): {media_file}")

        # FFmpeg command to just copy streams and pipe to Twitch (no encoding)
        ffmpeg_command = [
            "ffmpeg",
            "-loglevel", "error",  # Only show errors
            "-re",  # Ensure real-time streaming
            "-i", media_file,  # Input the preprocessed file
            "-c", "copy",  # Copy the video and audio without re-encoding
            "-f", "mpegts",  # Output format to pipe to Twitch
            "-"  # Pipe output to stdout
        ]

    else:
        # Normalize and pipe the video to the streaming FFmpeg instance
        print(f"Normalizing and streaming: {media_file}")

        # FFmpeg command to normalize the video and pipe it to stdout (H.264 and AAC)
        ffmpeg_command = [
            "ffmpeg",
            "-loglevel", "error",  # Only show errors
            "-i", media_file,  # Input video file
            "-s", "1280x720",  # Scale video to 720p
            "-c:v", "libx264",  # Video codec H.264
            "-b:v", "2300k",  # Reduce video bitrate
            "-g", "60",  # Keyframe interval
            "-r", "30",  # Frame rate
            "-c:a", "aac",  # Audio codec AAC
            "-ar", "44100",  # Audio sample rate
            "-f", "mpegts",  # Output format (MPEG-TS)
            "-"  # Pipe output to stdout
        ]

    # Start the normalization/preprocessing process and pipe its output to the streaming process
    normalize_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE)

    # Pipe data from the normalization/preprocessed process to the stream continuously
    while True:
        data = normalize_proc.stdout.read(65536)
        if not data:  # If no data, break the loop
            break
        stream_proc.stdin.write(data)  # Write normalized data to the streaming process

    normalize_proc.wait()


# Function to start streaming the videos
def normalize_and_stream(media_files, last_played_id=None):
    global stream_proc

    # Start the stream subprocess and keep it running
    print("Starting streaming process...")
    stream_proc = subprocess.Popen(stream_command, stdin=subprocess.PIPE)

    # Find the position of the last played video by id
    start_index = 0
    if last_played_id is not None:
        for i, media in enumerate(media_files):
            if media['id'] == last_played_id:
                start_index = i  # Start from the requested video
                break

    # Iterate through media files and normalize/pipe each clip starting from the last played id
    while True:  # Infinite loop to restart the playlist from the beginning
        idx = start_index
        while idx < len(media_files):
            media = media_files[idx]
            media_file = media.get('file_path')
            media_id = media.get('id')

            # Play a black screen transition between clips
            play_transition()

            # Check if the file has "_processed.mp4" in the name (indicating it is already processed)
            if "_processed.mp4" in media_file and os.path.exists(media_file):
                # Pipe preprocessed file to the streaming FFmpeg instance (no re-encoding)
                pipe_to_stream(media_file, is_preprocessed=True)
            else:
                # Normalize and pipe the non-preprocessed file
                pipe_to_stream(media_file, is_preprocessed=False)

            # Save progress after each clip is streamed
            save_progress(media_id)
            print(f"Progress saved. Last played video id: {media_id}.")
            idx += 1

        # If the playlist ends, start from the beginning again
        print("Reached the end of the playlist. Restarting from the beginning.")
        start_index = 0


# Main function to run the whole process
def main():
    # Check if a command-line argument (video ID) is passed
    if len(sys.argv) > 1:
        try:
            start_id = int(sys.argv[1])
            print(f"Starting from video ID: {start_id}")
        except ValueError:
            print("Invalid ID provided. Starting from the last saved position.")
            start_id = None
    else:
        start_id = None

    # Get media files from the playlist JSON
    print(f"Using playlist: {playlist_json}")
    media_files = get_media_files_from_playlist(playlist_json)

    if not media_files:
        print("No media files found in playlist!")
        return

    # Determine starting video: from command-line argument or last saved position
    last_played_id = start_id if start_id else load_progress()

    if last_played_id:
        print(f"Resuming from video id: {last_played_id}")
    else:
        print("Starting from the first video.")

    # Normalize and stream the clips starting from the last played id
    normalize_and_stream(media_files, last_played_id=last_played_id)


if __name__ == "__main__":
    main()

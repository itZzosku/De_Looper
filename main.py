import subprocess
import os
import json

# Twitch configuration
Twitch_Stream_Key = "live_1138107151_TllNxIhHwf0DI62aRS60XCA94YWrEN"
Twitch_URL = f"rtmp://live.twitch.tv/app/{Twitch_Stream_Key}"

# Define the path to playlist.json (in the same folder as main.py)
script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory where the script is located
playlist_json = os.path.join(script_dir, "playlist.json")


# Function to read playlist from the JSON file with UTF-8 encoding (for special characters)
def get_media_files_from_playlist(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:  # Ensure UTF-8 encoding
        data = json.load(f)
    return data.get("playlist", [])


# Function to build the FFmpeg command for normalizing the videos
def build_ffmpeg_normalization_command(media_files):
    # Input files for FFmpeg concat filter
    input_files = []
    for media in media_files:
        media_file = media.get('file_path')
        if os.path.exists(media_file):
            input_files.append(media_file)

    # FFmpeg command to normalize and concatenate
    normalize_command = [
        "ffmpeg",
        "-loglevel", "error",  # Only show errors
        "-re",  # Read input at the native frame rate
    ]

    # Add input files to FFmpeg command
    for media_file in input_files:
        normalize_command.extend(["-i", media_file])

    # Add the normalization filters
    filter_complex = []
    for index in range(len(input_files)):
        filter_complex.append(f"[{index}:v]scale=1280:720,fps=30[v{index}];")
        filter_complex.append(f"[{index}:a]aresample=44100[a{index}];")

    filter_complex.append(
        f"{''.join([f'[v{i}][a{i}]' for i in range(len(input_files))])}concat=n={len(input_files)}:v=1:a=1[v][a]")

    normalize_command.extend([
        "-filter_complex", "".join(filter_complex),  # Apply scaling, fps, and concat
        "-map", "[v]",  # Select video output
        "-map", "[a]",  # Select audio output
        "-c:v", "libx264",  # Encode video to H.264
        "-preset", "fast",  # Set encoding speed
        "-c:a", "aac",  # Encode audio to AAC
        "-f", "mpegts",  # Output format for piping
        "pipe:1"  # Pipe output to stdout
    ])

    return normalize_command


# Function to stream the normalized clips to Twitch
def stream_to_twitch():
    # FFmpeg command to stream to Twitch
    stream_command = [
        "ffmpeg",
        "-loglevel", "error",  # Only show errors
        "-re",  # Ensure real-time streaming
        "-i", "pipe:0",  # Read from the pipe (stdin)
        "-c:v", "copy",  # Copy the video stream without re-encoding (already normalized)
        "-c:a", "copy",  # Copy the audio stream without re-encoding
        "-f", "flv",  # Output format for Twitch
        Twitch_URL  # Streaming URL for Twitch
    ]

    return stream_command


# Main function to run the whole process
def main():
    # Get media files from the playlist JSON
    print(f"Using playlist: {playlist_json}")
    media_files = get_media_files_from_playlist(playlist_json)

    if not media_files:
        print("No media files found in playlist!")
        return

    # Build the FFmpeg normalization command
    normalize_command = build_ffmpeg_normalization_command(media_files)

    # Build the FFmpeg streaming command
    stream_command = stream_to_twitch()

    print("Starting normalization and streaming...")

    # Use subprocess to start both FFmpeg processes (one for normalization and one for streaming)
    with subprocess.Popen(normalize_command, stdout=subprocess.PIPE) as normalize_proc:
        # Pipe the output of the normalization process to the streaming process
        with subprocess.Popen(stream_command, stdin=normalize_proc.stdout):
            normalize_proc.wait()  # Wait for the normalization process to complete

    print("Stream ended.")


if __name__ == "__main__":
    main()

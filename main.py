import subprocess
import os
import json
import signal
import sys
import irc.client  # For sending messages to Twitch chat
import threading

# Global variables for processes
stream_proc = None
normalize_proc = None  # Ensure both are initialized at the module level
skip_event = threading.Event()  # Event to signal skipping the current clip

# Twitch configuration for streaming and chat
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_file, 'r', encoding='utf-8') as f:
    config_data = json.load(f)
    Twitch_Stream_Key = config_data.get("Twitch_Stream_Key")
    Twitch_OAuth_Token = config_data.get("Twitch_OAuth_Token")
    Twitch_Nick = config_data.get("Twitch_Nick")
    Twitch_Channel = config_data.get("Twitch_Channel")

Twitch_URL = f"rtmp://live.twitch.tv/app/{Twitch_Stream_Key}"

# Define the path to playlist.json and progress.json
script_dir = os.path.dirname(os.path.abspath(__file__))
playlist_json = os.path.join(script_dir, "playlist.json")
progress_json = os.path.join(script_dir, "progress.json")

# Global variable to hold the stream command
stream_command = [
    "ffmpeg",
    "-loglevel", "error",  # Only show errors
    "-re",  # Ensure real-time streaming
    "-i", "pipe:0",  # Read from stdin
    "-c:v", "libx264",  # Encode video to H.264
    "-c:a", "aac",  # Encode audio to AAC
    "-ar", "44100",  # Audio sample rate
    "-b:v", "2300k",  # Set video bitrate to 2300k
    "-maxrate", "2300k",
    "-g", "60",  # Keyframe interval
    "-flvflags", "no_duration_filesize",
    "-f", "flv",  # Output format for Twitch
    Twitch_URL
]

# Function to send a message to Twitch chat
def send_message_to_chat(message):
    client = irc.client.Reactor()
    try:
        c = client.server().connect("irc.chat.twitch.tv", 6667, Twitch_Nick, Twitch_OAuth_Token)
    except irc.client.ServerConnectionError as e:
        print(f"Error connecting to Twitch chat: {e}")
        return

    def on_connect(connection, event):
        connection.join(f"#{Twitch_Channel}")
        connection.privmsg(f"#{Twitch_Channel}", message)
        print(f"Sent message to Twitch chat: {message}")

    c.add_global_handler("welcome", on_connect)
    client.process_once(0.5)


# Function to play a 3-second black screen transition
def play_transition():
    ffmpeg_command = [
        "ffmpeg",
        "-f", "lavfi",
        "-loglevel", "error",
        "-i", "color=c=black:s=1280x720:r=30:d=3",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-ar", "44100",
        "-t", "3",
        "-f", "mpegts",
        "-"
    ]

    transition_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE)
    while True:
        data = transition_proc.stdout.read(65536)
        if not data:
            break
        stream_proc.stdin.write(data)
    transition_proc.wait()


# Function to read playlist from the JSON file with UTF-8 encoding
def get_media_files_from_playlist(json_file):
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("playlist", [])


# Function to save the last played id to progress.json
def save_progress(last_id):
    with open(progress_json, 'w', encoding='utf-8') as f:
        json.dump({"last_played_id": last_id}, f)
        f.flush()
        os.fsync(f.fileno())
    print(f"Progress saved. Last played video id: {last_id}.")


# Function to load the last played id from progress.json and return the next video (last_played_id + 1)
def load_progress():
    if os.path.exists(progress_json):
        with open(progress_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        last_played_id = data.get("last_played_id", None)
        if last_played_id is not None:
            return last_played_id + 1
    return None


# Graceful shutdown function
def graceful_shutdown(signum, frame):
    global stream_proc, normalize_proc
    print("Shutting down...")

    if normalize_proc and normalize_proc.poll() is None:
        normalize_proc.terminate()

    if stream_proc and stream_proc.poll() is None:
        stream_proc.stdin.close()
        stream_proc.terminate()


# Register the shutdown handler
signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)


# Function to monitor Twitch chat for skip votes
def monitor_chat(skip_event):
    client = irc.client.Reactor()

    try:
        c = client.server().connect("irc.chat.twitch.tv", 6667, Twitch_Nick, Twitch_OAuth_Token)
    except irc.client.ServerConnectionError as e:
        print(f"Error connecting to Twitch chat: {e}")
        return

    def on_pubmsg(connection, event):
        message = event.arguments[0].strip().lower()

        if message == "!skip":
            print("Received skip command from chat")
            skip_event.set()  # Trigger skip event
            send_message_to_chat("Skipping current clip!")

    c.add_global_handler("pubmsg", on_pubmsg)
    c.join(f"#{Twitch_Channel}")

    while True:
        client.process_once(0.2)


# Function to pipe media to the streaming FFmpeg instance
def pipe_to_stream(media_file, is_preprocessed):
    global stream_proc, normalize_proc, skip_event

    if is_preprocessed:
        print(f"Streaming preprocessed file: {media_file}")
        ffmpeg_command = [
            "ffmpeg",
            "-loglevel", "error",
            "-re",
            "-i", media_file,
            "-c", "copy",
            "-f", "mpegts",
            "-"
        ]
    else:
        print(f"Normalizing and streaming: {media_file}")
        ffmpeg_command = [
            "ffmpeg",
            "-loglevel", "error",
            "-i", media_file,
            "-s", "1280x720",
            "-c:v", "libx264",
            "-b:v", "2300k",
            "-g", "60",
            "-r", "30",
            "-c:a", "aac",
            "-ar", "44100",
            "-f", "mpegts",
            "-"
        ]

    normalize_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE)

    try:
        while True:
            data = normalize_proc.stdout.read(65536)
            if not data or skip_event.is_set():
                if skip_event.is_set():
                    print("Skip event detected. Terminating current clip.")
                    skip_event.clear()  # Reset the skip event
                break
            stream_proc.stdin.write(data)

    finally:
        if normalize_proc.poll() is None:
            normalize_proc.terminate()
            normalize_proc.wait()


# Function to stream media files and recheck playlist between clips
def stream_and_recheck_playlist(last_played_id=None):
    global stream_proc

    stream_proc = subprocess.Popen(stream_command, stdin=subprocess.PIPE)

    played_ids = set()  # To track the IDs that have been played

    while True:
        # Reload playlist before starting a new clip
        media_files = get_media_files_from_playlist(playlist_json)

        if not media_files:
            print("No media files found in playlist!")
            return

        start_index = 0
        if last_played_id is not None:
            for i, media in enumerate(media_files):
                if media['id'] == last_played_id:
                    start_index = i
                    break

        idx = start_index
        while idx < len(media_files):
            media = media_files[idx]
            media_file = media.get('file_path')
            media_id = media.get('id')
            media_title = media.get('name', 'Untitled')
            media_release_date = media.get('release_date', 'Unknown')

            if media_id in played_ids:
                # Skip videos that have already been played
                idx += 1
                continue

            played_ids.add(media_id)  # Mark this video as played

            message = f"Nyt toistetaan: {media_title} (Julkaisupäivä: {media_release_date})"
            send_message_to_chat(message)

            if "_processed.mp4" in media_file and os.path.exists(media_file):
                pipe_to_stream(media_file, is_preprocessed=True)
            else:
                pipe_to_stream(media_file, is_preprocessed=False)

            save_progress(media_id)
            play_transition()
            idx += 1

        print("Reached the end of the playlist. Rechecking for new clips...")
        last_played_id = None  # Reset to start from the first video on the next loop


# Main function to run the whole process
def main():
    if len(sys.argv) > 1:
        try:
            start_id = int(sys.argv[1])
            print(f"Starting from video ID: {start_id}")
        except ValueError:
            print("Invalid ID provided. Starting from the last saved position.")
            start_id = None
    else:
        start_id = None

    print(f"Using playlist: {playlist_json}")
    last_played_id = start_id if start_id else load_progress()

    if last_played_id:
        print(f"Resuming from video id: {last_played_id}")
    else:
        print("Starting from the first video.")

    # Start the chat monitoring thread
    chat_thread = threading.Thread(target=monitor_chat, args=(skip_event,))
    chat_thread.daemon = True  # Ensures the thread will exit when the main program exits
    chat_thread.start()

    stream_and_recheck_playlist(last_played_id=last_played_id)


if __name__ == "__main__":
    main()

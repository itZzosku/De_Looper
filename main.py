import subprocess
import os
import json
import signal
import sys
import threading
import socket  # For connecting to Twitch IRC chat

# Global variables for processes
stream_proc = None
normalize_proc = None
skip_event = threading.Event()  # Event to signal skipping the current clip

# Twitch configuration for streaming and chat
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(config_file, 'r', encoding='utf-8') as f:
    config_data = json.load(f)
    Twitch_Stream_Key = config_data.get("Twitch_Stream_Key")
    Twitch_OAuth_Token = config_data.get("Twitch_OAuth_Token")
    Twitch_Nick = config_data.get("Twitch_Nick")
    Twitch_Channel = config_data.get("Twitch_Channel")
    Instant_Skip_Users = config_data.get("Instant_Skip_Users", [])  # Load Instant_Skip_Users list

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
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('irc.chat.twitch.tv', 6667))
        s.send(f"PASS {Twitch_OAuth_Token}\r\n".encode('utf-8'))
        s.send(f"NICK {Twitch_Nick}\r\n".encode('utf-8'))
        s.send(f"JOIN #{Twitch_Channel}\r\n".encode('utf-8'))
        s.send(f"PRIVMSG #{Twitch_Channel} :{message}\r\n".encode('utf-8'))
        s.close()
        print(f"Sent message to Twitch chat: {message}")
    except Exception as e:
        print(f"Error sending message to Twitch chat: {e}")


# Function to play a 3-second black screen transition
def play_transition():
    global stream_proc

    # Ensure stream_proc is still valid and running before playing the transition
    if stream_proc is None or stream_proc.poll() is not None:
        print("Stream process is not running. Transition cannot be played.")
        return

    # Define the FFmpeg command to generate the 3-second black screen transition
    ffmpeg_command = [
        "ffmpeg",
        "-f", "lavfi",
        "-loglevel", "error",
        "-i", "color=c=black:s=1280x720:r=30:d=3",  # Black screen video
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",  # Silent audio
        "-c:v", "libx264",
        "-c:a", "aac",
        "-ar", "44100",
        "-t", "3",  # Duration of 3 seconds
        "-f", "mpegts",
        "-"
    ]

    # Start the transition process
    transition_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        while True:
            # Read from the transition process output
            data = transition_proc.stdout.read(65536)
            if not data:
                break

            # Check if stream_proc is still running before writing to stdin
            if stream_proc and stream_proc.stdin and stream_proc.poll() is None:
                try:
                    stream_proc.stdin.write(data)
                except (BrokenPipeError, ValueError):
                    print("Stream process was closed during transition.")
                    break
            else:
                print("Stream process was closed during transition.")
                break

    finally:
        # Wait for the transition process to finish
        transition_proc.wait()

        # Flush, but DO NOT close the stream_proc stdin to keep it alive
        if stream_proc and stream_proc.stdin and stream_proc.poll() is None:
            try:
                stream_proc.stdin.flush()  # Ensure any remaining data is flushed
            except (BrokenPipeError, ValueError):
                print("Broken pipe or ValueError when flushing stream after transition.")
        else:
            print("Stream process already closed, cannot flush.")


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
        try:
            normalize_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("normalize_proc did not terminate in time. Killing it.")
            normalize_proc.kill()
            normalize_proc.wait()

    if stream_proc and stream_proc.poll() is None:
        if stream_proc.stdin:
            try:
                stream_proc.stdin.close()
            except Exception as e:
                print(f"Error closing stream_proc.stdin: {e}")
        stream_proc.terminate()
        try:
            stream_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("stream_proc did not terminate in time. Killing it.")
            stream_proc.kill()
            stream_proc.wait()

    sys.exit(0)


# Register the shutdown handler
signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)


# Monitor chat for skip votes and trigger skip event when threshold is met
def monitor_chat(skip_event):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('irc.chat.twitch.tv', 6667))
        s.send(f"PASS {Twitch_OAuth_Token}\r\n".encode('utf-8'))
        s.send(f"NICK {Twitch_Nick}\r\n".encode('utf-8'))
        s.send(f"JOIN #{Twitch_Channel}\r\n".encode('utf-8'))
        print("Connected to Twitch IRC.")
    except Exception as e:
        print(f"Error connecting to Twitch IRC: {e}")
        return

    skip_votes = set()
    skip_threshold = 3

    buffer = ""
    while True:
        try:
            response = s.recv(2048).decode('utf-8')
            if not response:
                print("Disconnected from Twitch IRC.")
                break

            buffer += response
            while '\r\n' in buffer:
                line, buffer = buffer.split('\r\n', 1)
                if line.startswith('PING'):
                    s.send("PONG\r\n".encode('utf-8'))
                    continue

                # Parse the IRC message
                parts = line.split(' ')
                if len(parts) < 4:
                    continue

                if parts[1] == 'PRIVMSG':
                    username = parts[0].split('!')[0][1:]
                    channel = parts[2]
                    message = ' '.join(parts[3:])[1:]

                    # Handle the skip command
                    if message.strip().lower() == '!skip':
                        username = username.lower()
                        if username in [user.lower() for user in Instant_Skip_Users]:
                            print(f"{username} is an instant skip user. Skipping immediately.")
                            skip_event.set()  # Trigger skip
                            send_message_to_chat(f"{username} skipped the current clip!")
                        else:
                            if username not in skip_votes:
                                skip_votes.add(username)
                                print(f"{username} voted to skip. Total votes: {len(skip_votes)}")

                            if len(skip_votes) >= skip_threshold:
                                print(f"Skip threshold reached with {len(skip_votes)} votes. Skipping the clip.")
                                skip_event.set()
                                send_message_to_chat(
                                    f"Skip threshold reached with {len(skip_votes)} votes! Skipping the current clip.")
                                skip_votes.clear()
        except Exception as e:
            print(f"Error in monitor_chat: {e}")
            continue


# Function to pipe media to the streaming FFmpeg instance
def pipe_to_stream(media_file, is_preprocessed):
    global stream_proc, normalize_proc, skip_event

    if is_preprocessed:
        print(f"Streaming preprocessed file: {media_file}")
        ffmpeg_command = [
            "ffmpeg",
            "-loglevel", "error",
            "-re",  # Ensure real-time streaming
            "-i", media_file,
            "-c", "copy",  # Avoid re-encoding for preprocessed files
            "-f", "mpegts",
            "-"
        ]
    else:
        print(f"Normalizing and streaming: {media_file}")
        ffmpeg_command = [
            "ffmpeg",
            "-loglevel", "error",
            "-i", media_file,
            "-s", "1280x720",  # Set resolution
            "-c:v", "libx264",
            "-b:v", "2300k",
            "-g", "60",
            "-r", "30",
            "-c:a", "aac",
            "-ar", "44100",
            "-f", "mpegts",
            "-"
        ]

    # Start FFmpeg to process the media file
    normalize_proc = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"Started normalize_proc with PID: {normalize_proc.pid}")

    try:
        while True:
            data = normalize_proc.stdout.read(65536)
            if not data or skip_event.is_set():
                if skip_event.is_set():
                    print("Skip event detected. Terminating current clip.")
                    skip_event.clear()  # Reset the skip event
                break

            # Write the data to stream_proc stdin (continuous streaming)
            if stream_proc and stream_proc.stdin and stream_proc.poll() is None:
                try:
                    stream_proc.stdin.write(data)
                except (BrokenPipeError, ValueError) as e:
                    print(f"Error writing to stream_proc.stdin: {e}")
                    break
            else:
                print("Stream process was closed during media playback.")
                break

    except Exception as e:
        print(f"An error occurred in pipe_to_stream: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if normalize_proc and normalize_proc.poll() is None:
            print("Terminating normalize_proc...")
            normalize_proc.terminate()
            try:
                normalize_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("normalize_proc did not terminate in time. Killing it.")
                normalize_proc.kill()
                normalize_proc.wait()

        # Flush but don't close stream_proc to keep it running
        if stream_proc and stream_proc.stdin:
            try:
                stream_proc.stdin.flush()  # Ensure any remaining data is flushed
            except (BrokenPipeError, ValueError):
                print("Broken pipe when flushing stream after media playback.")


# Function to stream media files and recheck playlist between clips
def stream_and_recheck_playlist(last_played_id=None):
    global stream_proc

    # Ensure stream_proc is started once and kept alive throughout
    if stream_proc is None or stream_proc.poll() is not None:
        print("Starting stream process.")
        stream_proc = subprocess.Popen(stream_command, stdin=subprocess.PIPE)
        print(f"Started stream_proc with PID: {stream_proc.pid}")

    played_ids = set()  # To track the IDs that have been played

    while True:
        try:
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

                print(f"Starting playback of media ID {media_id}: {media_title}")
                message = f"Nyt toistetaan: {media_title} (Julkaisupäivä: {media_release_date})"
                send_message_to_chat(message)

                if "_processed.mp4" in media_file and os.path.exists(media_file):
                    pipe_to_stream(media_file, is_preprocessed=True)
                else:
                    pipe_to_stream(media_file, is_preprocessed=False)

                save_progress(media_id)
                play_transition()  # Ensure the transition plays between videos
                print(f"Finished processing media ID {media_id}. Moving to the next clip.")
                idx += 1

            print("Reached the end of the playlist. Rechecking for new clips...")
            last_played_id = None  # Reset to start from the first video on the next loop

        except Exception as e:
            print(f"An error occurred in stream_and_recheck_playlist: {e}")
            import traceback
            traceback.print_exc()
            # Decide whether to break or continue based on the exception
            break


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
    print("Starting chat monitoring thread.")
    chat_thread = threading.Thread(target=monitor_chat, args=(skip_event,))
    chat_thread.daemon = True  # Ensures the thread will exit when the main program exits
    chat_thread.start()

    stream_and_recheck_playlist(last_played_id=last_played_id)


if __name__ == "__main__":
    main()

import argparse
import subprocess
import os
import json
import signal
import sys
import threading
import socket  # For connecting to Twitch IRC chat
import time  # For tracking stream duration


def print_ts(message):
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"[{current_time}] {message}")


# Global variables for processes
stream_proc = None
normalize_proc = None
skip_event = threading.Event()  # Event to signal skipping the current clip
stream_start_time = None  # Variable to track when stream_proc was started

# Maximum stream duration before restarting (e.g., 47 hours)
max_stream_duration = 47 * 60 * 60  # 47 hours in seconds

# Argument parser for config file and starting videoNumber
parser = argparse.ArgumentParser(description="Stream automation script")
parser.add_argument(
    "--config",
    default="config.json",
    help="Specify the configuration file to use (default: config.json)"
)
parser.add_argument(
    "--video_number",
    type=int,
    help="Starting videoNumber (default: last saved position)"
)
args = parser.parse_args()

# Load configuration file
config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), args.config)
print(f"Using configuration file: {config_file}")
with open(config_file, 'r', encoding='utf-8') as f:
    config_data = json.load(f)
    Twitch_Stream_Key = config_data.get("Twitch_Stream_Key")
    Twitch_OAuth_Token = config_data.get("Twitch_OAuth_Token")
    Twitch_Nick = config_data.get("Twitch_Nick")
    Twitch_Channel = config_data.get("Twitch_Channel")
    Instant_Skip_Users = config_data.get("Instant_Skip_Users", [])

# Determine starting videoNumber
start_id = args.video_number if args.video_number is not None else None
if start_id is not None:
    print(f"Starting from videoNumber: {start_id}")
else:
    print("No video_number provided, will use last saved position.")

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
    "-reconnect", "1",  # Enable automatic reconnection
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
        print_ts(f"Sent message to Twitch chat: {message}")
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


# Function to save the last played videoNumber to progress.json
def save_progress(last_video_number):
    with open(progress_json, 'w', encoding='utf-8') as f:
        json.dump({"last_played_videoNumber": last_video_number}, f, indent=4, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    print_ts(f"Progress saved. Last played videoNumber: {last_video_number}.")


# Function to load the last played videoNumber from progress.json
def load_progress():
    if os.path.exists(progress_json):
        try:
            with open(progress_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            last_played_videoNumber = data.get("last_played_videoNumber", None)
            return last_played_videoNumber
        except json.JSONDecodeError:
            print(f"Warning: The progress file '{progress_json}' is empty or invalid. Starting from the beginning.")
            return None
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
                        username_lower = username.lower()
                        instant_skip_users_lower = [user.lower() for user in Instant_Skip_Users]
                        if username_lower in instant_skip_users_lower:
                            print(f"{username} is an instant skip user. Skipping immediately.")
                            skip_event.set()  # Trigger skip
                            send_message_to_chat(f"{username} skipped the current clip!")
                        else:
                            if username_lower not in skip_votes:
                                skip_votes.add(username_lower)
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
        print_ts(f"Streaming preprocessed file: {media_file}")
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
            "-re",  # Ensure real-time streaming
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
    print_ts(f"Started normalize_proc with PID: {normalize_proc.pid}")

    try:
        while True:
            data = normalize_proc.stdout.read(65536)
            if data:
                # Write the data to stream_proc stdin
                if stream_proc and stream_proc.stdin and stream_proc.poll() is None:
                    try:
                        stream_proc.stdin.write(data)
                    except (BrokenPipeError, ValueError) as e:
                        print(f"Error writing to stream_proc.stdin: {e}")
                        break
                else:
                    print("Stream process was closed during media playback.")
                    break
            else:
                # No data was read
                if normalize_proc.poll() is not None:
                    print_ts("normalize_proc has finished processing the clip.")

                    # Read any remaining data from normalize_proc.stdout
                    remaining_data = normalize_proc.stdout.read()
                    while remaining_data:
                        if stream_proc and stream_proc.stdin and stream_proc.poll() is None:
                            try:
                                stream_proc.stdin.write(remaining_data)
                            except (BrokenPipeError, ValueError) as e:
                                print(f"Error writing remaining data to stream_proc.stdin: {e}")
                                break
                        remaining_data = normalize_proc.stdout.read()

                    break
                elif skip_event.is_set():
                    print("Skip event detected. Terminating current clip.")
                    skip_event.clear()  # Reset the skip event
                    # Terminate normalize_proc due to skip event
                    if normalize_proc and normalize_proc.poll() is None:
                        print("Terminating normalize_proc due to skip event...")
                        normalize_proc.terminate()
                        try:
                            normalize_proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            print("normalize_proc did not terminate in time. Killing it.")
                            normalize_proc.kill()
                            normalize_proc.wait()
                    # Play the transition after skipping
                    play_transition()
                    return  # Exit the function
                else:
                    # No data available yet, wait a bit
                    time.sleep(0.1)
    except Exception as e:
        print(f"An error occurred in pipe_to_stream: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Wait for normalize_proc to finish naturally
        if normalize_proc and normalize_proc.poll() is None:
            print("Waiting for normalize_proc to finish...")
            normalize_proc.wait()

        # Flush but don't close stream_proc to keep it running
        if stream_proc and stream_proc.stdin:
            try:
                stream_proc.stdin.flush()  # Ensure any remaining data is flushed
            except (BrokenPipeError, ValueError):
                print("Broken pipe when flushing stream after media playback.")

    # Play the transition after the clip has fully played
    play_transition()


# Function to stream media files and recheck playlist between clips
def stream_and_recheck_playlist(last_played_videoNumber=None):
    global stream_proc, stream_start_time

    # Ensure stream_proc is started once and kept alive throughout
    if stream_proc is None or stream_proc.poll() is not None:
        print("Starting stream process.")
        stream_proc = subprocess.Popen(stream_command, stdin=subprocess.PIPE)
        stream_start_time = time.time()
        print(f"Started stream_proc with PID: {stream_proc.pid}")

    played_ids = set()  # To track the IDs that have been played

    while True:
        try:
            # Reload playlist before starting a new clip
            media_files = get_media_files_from_playlist(playlist_json)

            if not media_files:
                print("No media files found in playlist!")
                return

            # Determine the starting index based on last_played_videoNumber
            start_index = 0
            if last_played_videoNumber is not None:
                for i, media in enumerate(media_files):
                    if media.get('videoNumber') == last_played_videoNumber:
                        start_index = i + 1  # Start from the next video
                        print(
                            f"Found last played videoNumber {last_played_videoNumber} at index {i}. Starting from index {start_index}.")
                        break
                else:
                    print(
                        f"Last played videoNumber {last_played_videoNumber} not found in playlist. Starting from the beginning.")
                    start_index = 0

            idx = start_index
            while idx < len(media_files):
                media = media_files[idx]
                media_file = media.get('file_path')
                media_id = media.get('videoNumber')
                media_title = media.get('name', 'Untitled')
                media_release_date = media.get('release_date', 'Unknown')

                if media_id in played_ids:
                    # Skip videos that have already been played
                    idx += 1
                    continue

                played_ids.add(media_id)  # Mark this video as played
                print_ts(f"Starting playback of mediaNumber {media_id}: {media_title}")
                youtube_link = media.get('youtube_link', '')
                if youtube_link:
                    message = (
                        f"Nyt toistetaan: {media_title} "
                        f"(Julkaisupäivä: {media_release_date}) "
                        f"{youtube_link}"
                    )
                else:
                    message = f"Nyt toistetaan: {media_title} (Julkaisupäivä: {media_release_date})"
                send_message_to_chat(message)

                if "_processed.mp4" in media_file and os.path.exists(media_file):
                    pipe_to_stream(media_file, is_preprocessed=True)
                else:
                    pipe_to_stream(media_file, is_preprocessed=False)

                print_ts(f"Finished processing mediaNumber {media_id}. Moving to the next clip.")
                save_progress(media_id)

                # Check if we need to restart the stream_proc to avoid Twitch's 48h limit
                if time.time() - stream_start_time > max_stream_duration:
                    print("Stream has been running for more than maximum duration. Restarting stream_proc.")

                    # Gracefully terminate stream_proc
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

                    # Start a new stream_proc
                    print("Starting new stream process.")
                    stream_proc = subprocess.Popen(stream_command, stdin=subprocess.PIPE)
                    stream_start_time = time.time()
                    print(f"Started new stream_proc with PID: {stream_proc.pid}")

                idx += 1

            print("Reached the end of the playlist. Rechecking for new clips...")
            last_played_videoNumber = None  # Reset to start from the first video on the next loop

        except Exception as e:
            print(f"An error occurred in stream_and_recheck_playlist: {e}")
            import traceback
            traceback.print_exc()
            break


# Main function to run the whole process
def main():
    print(f"Using playlist: {playlist_json}")

    # Use `start_id` if provided; otherwise, load from progress.json
    last_played_videoNumber = start_id if start_id is not None else load_progress()

    if last_played_videoNumber:
        print(f"Resuming from videoNumber: {last_played_videoNumber}")
    else:
        print("Starting from the first video.")

    # Start the chat monitoring thread
    print("Starting chat monitoring thread.")
    chat_thread = threading.Thread(target=monitor_chat, args=(skip_event,))
    chat_thread.daemon = True  # Ensures the thread will exit when the main program exits
    chat_thread.start()

    # Call function to start streaming based on the last played video
    stream_and_recheck_playlist(last_played_videoNumber=last_played_videoNumber)


if __name__ == "__main__":
    main()

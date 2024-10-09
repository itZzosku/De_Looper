import os
import subprocess
import argparse
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event

# Create a global event to handle shutdown
shutdown_event = Event()


def preprocess_file(input_file, output_file, codec):
    if shutdown_event.is_set():
        return False

    if not os.path.exists(input_file):
        print(f"Error: Input file does not exist: {input_file}")
        return False

    video_codec = 'h264_nvenc' if codec == "h264_nvenc" else 'libx264'

    try:
        subprocess.run([
            'ffmpeg',
            '-y',
            '-loglevel', 'error',
            '-i', input_file,
            '-s', '1280x720',
            '-c:v', video_codec, '-preset', 'fast', '-b:v', '2300k',
            '-r', '30',
            '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',
            '-movflags', '+faststart',
            output_file
        ], check=True)
        print(f"Preprocessing complete: {output_file}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error preprocessing file {input_file}: {e}")
        return False


def process_video_file(file_path, codec, index, total_videos):
    if shutdown_event.is_set():
        return False

    directory, filename = os.path.split(file_path)
    input_file = file_path
    output_file = os.path.join(directory, filename.replace('.mp4', '_processed.mp4'))

    print(f"Processing {index}/{total_videos}: {input_file}")
    success = preprocess_file(input_file, output_file, codec)

    if success:
        try:
            os.remove(input_file)
            print(f"Original file deleted, and preprocessed file saved as: {output_file}")
        except OSError as e:
            print(f"Error deleting original file {input_file}: {e}")
            return False
        return True
    else:
        print(f"Failed to preprocess {input_file}. Skipping.")
        return False


def preprocess_videos(directories, codec, max_workers=2):
    directories = [os.path.normpath(d) for d in directories]

    video_files = []
    for directory in directories:
        if not os.path.isdir(directory):
            print(f"Error: The directory '{directory}' does not exist.")
            continue
        with os.scandir(directory) as entries:
            for entry in entries:
                if shutdown_event.is_set():
                    print("Shutdown signal received. Stopping new tasks.")
                    break
                if entry.is_file() and entry.name.endswith('.mp4') and not entry.name.endswith('_processed.mp4'):
                    video_files.append(entry.path)

    total_videos = len(video_files)
    if total_videos == 0:
        print("No videos to preprocess in the specified directories.")
        return

    processed_videos = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(process_video_file, file_path, codec, index, total_videos): file_path
            for index, file_path in enumerate(video_files, start=1)
        }

        for future in as_completed(future_to_file):
            filename = future_to_file[future]
            try:
                result = future.result()
                if result:
                    processed_videos += 1
            except Exception as e:
                print(f"Exception occurred while processing {filename}: {e}")

            if shutdown_event.is_set():
                print("Shutdown in progress. Waiting for remaining tasks to finish...")
                break

    print(f"Preprocessing complete. {processed_videos} out of {total_videos} videos were processed.")


def signal_handler(sig, frame):
    print(f"Received signal {sig}. Initiating graceful shutdown...")
    shutdown_event.set()


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Preprocess video files in specified directories.")
    parser.add_argument('--video_folders', nargs='+', default=None, type=str,
                        help="List of directories containing video files to preprocess")
    parser.add_argument('--codec', default=None, choices=['h264_nvenc', 'libx264'],
                        help="Video encoder (h264_nvenc for GPU, libx264 for CPU)")
    parser.add_argument('--max_workers', default=2, type=int,
                        help="Maximum number of parallel workers")

    args = parser.parse_args()

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.video_folders is None:
        folders_input = input("Enter the directories containing video files to preprocess (separated by spaces): ")
        args.video_folders = folders_input.strip().split()

    if args.codec is None:
        codec_choice = input("Select codec: 1 for h264_nvenc (NVIDIA GPU), 2 for libx264 (CPU): ").strip()
        if codec_choice == '1':
            args.codec = 'h264_nvenc'
        elif codec_choice == '2':
            args.codec = 'libx264'
        else:
            print("Invalid choice! Defaulting to libx264.")
            args.codec = 'libx264'

    valid_directories = [os.path.normpath(d) for d in args.video_folders if os.path.isdir(os.path.normpath(d))]
    if not valid_directories:
        print("Error: None of the specified directories exist.")
        return

    preprocess_videos(valid_directories, args.codec, args.max_workers)


if __name__ == '__main__':
    main()

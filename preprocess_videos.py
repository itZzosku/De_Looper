import os
import subprocess
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed


def preprocess_file(input_file, output_file, codec):
    # Check if input file exists before attempting to preprocess
    if not os.path.exists(input_file):
        print(f"Error: Input file does not exist: {input_file}")
        return False

    # Set encoding parameters based on the codec
    video_codec = 'h264_nvenc' if codec == "h264_nvenc" else 'libx264'

    # Run ffmpeg with the selected codec
    try:
        subprocess.run([
            'ffmpeg',
            '-y',
            '-loglevel', 'error',
            '-i', input_file,
            '-s', '1280x720',  # Scale to 720p
            '-c:v', video_codec, '-preset', 'fast', '-b:v', '2300k',
            '-r', '30',  # Set frame rate to 30fps
            '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',  # AAC audio
            '-movflags', '+faststart',  # Fast start for streaming
            output_file
        ], check=True)
        print(f"Preprocessing complete: {output_file}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error preprocessing file {input_file}: {e}")
        return False


def process_video_file(file_path, codec, index, total_videos):
    directory, filename = os.path.split(file_path)
    input_file = file_path
    output_file = os.path.join(directory, filename.replace('.mp4', '_processed.mp4'))

    print(f"Processing {index}/{total_videos}: {input_file}")

    # Preprocess the file using the preprocess_file function
    success = preprocess_file(input_file, output_file, codec)

    if success:
        # Remove the original file after preprocessing
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


def preprocess_videos(directories, codec, max_workers=4):
    # Normalize directory paths
    directories = [os.path.normpath(d) for d in directories]

    # Collect all video files from the specified directories
    video_files = []
    for directory in directories:
        if not os.path.isdir(directory):
            print(f"Error: The directory '{directory}' does not exist.")
            continue
        # Use os.scandir for better performance
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_file() and entry.name.endswith('.mp4') and not entry.name.endswith('_processed.mp4'):
                    video_files.append(entry.path)

    total_videos = len(video_files)
    if total_videos == 0:
        print("No videos to preprocess in the specified directories.")
        return

    processed_videos = 0

    # Use ThreadPoolExecutor to process videos in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks to the executor
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

    # Final summary
    print(f"Preprocessing complete. {processed_videos} out of {total_videos} videos were processed.")


def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Preprocess video files in specified directories.")
    parser.add_argument('--video_folders', nargs='+', default=None, type=str,
                        help="List of directories containing video files to preprocess")
    parser.add_argument('--codec', default=None, choices=['h264_nvenc', 'libx264'],
                        help="Video encoder (h264_nvenc for GPU, libx264 for CPU)")
    parser.add_argument('--max_workers', default=4, type=int,
                        help="Maximum number of parallel workers")

    args = parser.parse_args()

    # If arguments are not provided, prompt the user for input
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

    # Normalize and validate directories
    valid_directories = [os.path.normpath(d) for d in args.video_folders if os.path.isdir(os.path.normpath(d))]
    if not valid_directories:
        print("Error: None of the specified directories exist.")
        return

    # Start preprocessing videos with the specified number of workers
    preprocess_videos(valid_directories, args.codec, args.max_workers)


if __name__ == '__main__':
    main()

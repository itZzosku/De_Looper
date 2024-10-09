import os
import subprocess
import argparse
import ytdlp_prerun  # Import the module that checks and updates videos.json
from common_functions import sanitize_filename
from common_functions import get_unix_timestamp_and_date_string  # Updated to use the combined function
from common_functions import load_videos_json  # Using the updated load_videos_json
from common_functions import check_existing_file
from common_functions import filter_videos_by_date


def preprocess_file(input_file, output_file, codec):
    # Check if input file exists before attempting to preprocess
    if not os.path.exists(input_file):
        print(f"Error: Input file does not exist: {input_file}")
        return

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
    except subprocess.CalledProcessError as e:
        print(f"Error preprocessing file {input_file}: {e}")


def download_and_preprocess_videos(videos, download_path, codec):
    # Define the archive file path in the same folder as the downloaded videos
    archive_path = os.path.join(download_path, "archive.txt")

    total_videos = len(videos)
    processed_videos = 0
    skipped_videos = 0  # Track skipped videos

    # Download and process each video
    for index, video in enumerate(videos, start=1):
        video_id = video['id']
        video_title = sanitize_filename(video['name'])  # Sanitize the video title to avoid file naming issues
        published_at = video['publishedAt']

        # Generate the Unix timestamp and date string
        unix_timestamp, date_string = get_unix_timestamp_and_date_string(published_at)

        # Create the custom file name: "timestamp_date_video_title.ext"
        output_template = f"{download_path}/{unix_timestamp}_{date_string}_{video_title}"
        downloaded_file = f"{output_template}.mp4"
        processed_file = f"{output_template}_processed.mp4"

        # Check if the video has already been downloaded or processed by comparing video titles
        existing_processed_file = check_existing_file(video_title, download_path)
        if existing_processed_file:
            print(f"Processed file already exists: {existing_processed_file}. Skipping download and processing.")
            skipped_videos += 1  # Increment skipped video count
            # Display progress, including skipped files
            print(f"Progress: {index}/{total_videos} videos processed or skipped.")
            continue

        # Use yt-dlp to download the video only if it doesn't exist
        yt_dlp_command = [
            'yt-dlp', '--download-archive', archive_path,
            '-o', f"{output_template}.%(ext)s", f"https://www.youtube.com/watch?v={video_id}"
        ]
        try:
            subprocess.run(yt_dlp_command, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error downloading video {video_title}: {e}")
            skipped_videos += 1
            print(f"Progress: {index}/{total_videos} videos processed or skipped.")
            continue

        # Check if the video was actually downloaded
        if not os.path.exists(downloaded_file):
            print(f"Video {video_title} was skipped or failed to download. Moving to the next one.")
            skipped_videos += 1
            print(f"Progress: {index}/{total_videos} videos processed or skipped.")
            continue

        print(f"Downloaded or found existing file: {downloaded_file}")

        # Preprocess the downloaded file
        preprocess_file(downloaded_file, processed_file, codec)

        # Remove the original file after preprocessing
        if os.path.exists(downloaded_file):
            os.remove(downloaded_file)
            print(f"Original file deleted: {downloaded_file}")

        # Increment the processed video count and show progress
        processed_videos += 1
        print(f"Progress: {index}/{total_videos} videos processed or skipped.")

    # Final summary
    print(f"Processing complete. {processed_videos} videos processed, {skipped_videos} videos skipped.")


def main():
    # Call the function from the imported module to ensure videos.json is up-to-date
    ytdlp_prerun.check_and_update_videos_json()

    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Download and preprocess videos.")

    # Changed arguments to use '--' format
    parser.add_argument('--start_date', default=None, type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument('--end_date', default=None, type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument('--folder', default=None, type=str, help="Download path")
    parser.add_argument('--codec', default=None, choices=['h264_nvenc', 'libx264'],
                        help="Video encoder (h264_nvenc for GPU, libx264 for CPU)")

    # Parse the arguments from the command line
    args = parser.parse_args()

    # If arguments are not provided, prompt the user for input
    if args.start_date is None:
        args.start_date = input("Enter the start date (YYYY-MM-DD): ")

    if args.end_date is None:
        args.end_date = input("Enter the end date (YYYY-MM-DD): ")

    if args.folder is None:
        args.folder = input("Enter the download path: ")

    if args.codec is None:
        codec_choice = input("Select codec: 1 for h264_nvenc (NVIDIA GPU), 2 for libx264 (CPU): ").strip()
        if codec_choice == '1':
            args.codec = 'h264_nvenc'
        elif codec_choice == '2':
            args.codec = 'libx264'
        else:
            print("Invalid choice! Defaulting to libx264.")
            args.codec = 'libx264'

    # Ensure the download path exists, create if not
    if not os.path.exists(args.folder):
        os.makedirs(args.folder)

    # Load videos from the JSON file
    videos = load_videos_json()  # Updated function call

    # Filter videos by the date range provided by the user
    filtered_videos = filter_videos_by_date(videos, args.start_date, args.end_date)

    # Print how many videos will be downloaded
    video_count = len(filtered_videos)
    if video_count == 0:
        print(f"No videos found between {args.start_date} and {args.end_date}.")
        return
    else:
        print(f"{video_count} videos will be downloaded from {args.start_date} to {args.end_date}.")

    # Download and preprocess the videos
    download_and_preprocess_videos(filtered_videos, args.folder, args.codec)

    # Print a success message
    print(f"Downloaded and preprocessed videos from {args.start_date} to {args.end_date} to {args.folder}.")


if __name__ == "__main__":
    main()

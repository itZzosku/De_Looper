import json
from datetime import datetime
import os
import re
import subprocess
import argparse


def load_videos_from_json(filename='videos.json'):
    # Load video data from a JSON file
    with open(filename, 'r', encoding='utf-8') as json_file:
        videos = json.load(json_file)
    return videos


def filter_videos_by_date(videos, start_date, end_date):
    # Convert string dates to datetime objects
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')

    # Filter videos by date range
    filtered_videos = [
        video for video in videos
        if start_date <= datetime.strptime(video['publishedAt'], '%Y-%m-%dT%H:%M:%SZ') <= end_date
    ]

    return filtered_videos


def get_unix_timestamp(published_at):
    # Convert publishedAt string to Unix timestamp
    dt = datetime.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ')
    return int(dt.timestamp())


def get_date_string(published_at):
    # Convert publishedAt string to YYYYMMDD format
    dt = datetime.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ')
    return dt.strftime('%Y%m%d')


def sanitize_filename(title):
    # Replace problematic characters (e.g., slashes, colons, etc.) with hyphens
    return re.sub(r'[\\/:"*?<>|]', '-', title)


def preprocess_file(input_file, output_file, encoder):
    # Check if input file exists before attempting to preprocess
    if not os.path.exists(input_file):
        print(f"Error: Input file does not exist: {input_file}")
        return

    # Set encoding parameters based on the encoder
    if encoder == "h264_nvenc":
        video_codec = 'h264_nvenc'
    else:
        video_codec = 'libx264'

    # Run ffmpeg with the selected encoder
    try:
        subprocess.run([
            'ffmpeg',
            '-loglevel', 'error',
            '-i', input_file,
            '-s', '1280x720',  # Scale to 720p
            '-c:v', video_codec, '-preset', 'fast', '-b:v', '2300k',  # Use the chosen encoder
            '-r', '30',  # Set frame rate to 30fps
            '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',  # AAC audio
            '-movflags', '+faststart',  # Fast start for streaming
            output_file
        ])
        print(f"Preprocessing complete: {output_file}")
    except Exception as e:
        print(f"Error preprocessing file {input_file}: {e}")


def check_existing_file(video_title, download_path):
    # Sanitize the video title to match how filenames are sanitized
    sanitized_video_title = sanitize_filename(video_title)

    for file in os.listdir(download_path):
        if file.endswith("_processed.mp4"):
            # Extract the part of the filename that contains the video title
            file_title = file.split('_', 2)[-1].rsplit('_', 1)[0]  # Extracts 'Näin paukuteltiin' from the filename

            if file_title == sanitized_video_title:
                return os.path.join(download_path, file)  # Return the full path if a match is found
    return None


def download_and_preprocess_videos(videos, download_path, encoder):
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

        # Generate the timestamp and date string
        unix_timestamp = get_unix_timestamp(published_at)
        date_string = get_date_string(published_at)

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
        yt_dlp_command = (
            f'yt-dlp --download-archive "{archive_path}" '
            f'-o "{output_template}.%(ext)s" https://www.youtube.com/watch?v={video_id}'
        )
        download_result = os.system(yt_dlp_command)

        # Check if the video was actually downloaded
        if not os.path.exists(downloaded_file):
            print(f"Video {video_title} was skipped or failed to download. Moving to the next one.")
            skipped_videos += 1
            print(f"Progress: {index}/{total_videos} videos processed or skipped.")
            continue

        print(f"Downloaded or found existing file: {downloaded_file}")

        # Preprocess the downloaded file
        preprocess_file(downloaded_file, processed_file, encoder)

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
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Download and preprocess videos.")
    parser.add_argument('start_date', nargs='?', default=None, type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument('end_date', nargs='?', default=None, type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument('download_path', nargs='?', default=None, type=str, help="Download path")
    parser.add_argument('encoder', nargs='?', default=None, choices=['h264_nvenc', 'libx264'],
                        help="Video encoder (h264_nvenc for GPU, libx264 for CPU)")

    # Parse the arguments from the command line
    args = parser.parse_args()

    # If arguments are not provided, prompt the user for input
    if args.start_date is None:
        args.start_date = input("Enter the start date (YYYY-MM-DD): ")

    if args.end_date is None:
        args.end_date = input("Enter the end date (YYYY-MM-DD): ")

    if args.download_path is None:
        args.download_path = input("Enter the download path: ")

    if args.encoder is None:
        encoder_choice = input("Select encoder: 1 for h264_nvenc (NVIDIA GPU), 2 for libx264 (CPU): ").strip()
        if encoder_choice == '1':
            args.encoder = 'h264_nvenc'
        elif encoder_choice == '2':
            args.encoder = 'libx264'
        else:
            print("Invalid choice! Defaulting to libx264.")
            args.encoder = 'libx264'

    # Ensure the download path exists, create if not
    if not os.path.exists(args.download_path):
        os.makedirs(args.download_path)

    # Load videos from the JSON file
    videos = load_videos_from_json()

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
    download_and_preprocess_videos(filtered_videos, args.download_path, args.encoder)

    # Print a success message
    print(f"Downloaded and preprocessed videos from {args.start_date} to {args.end_date} to {args.download_path}.")


if __name__ == "__main__":
    main()

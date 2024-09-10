import json
from datetime import datetime
import os
import re
import subprocess


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


def preprocess_file(input_file, output_file):
    # Check if input file exists before attempting to preprocess
    if not os.path.exists(input_file):
        print(f"Error: Input file does not exist: {input_file}")
        return

    # Run ffmpeg with the given parameters
    try:
        subprocess.run([
            'ffmpeg',
            '-loglevel', 'error',
            '-i', input_file,
            '-s', '1280x720',  # Scale to 720p
            '-c:v', 'h264_nvenc', '-preset', 'fast', '-b:v', '2300k',  # Use h264_nvenc for GPU encoding
            '-r', '30',  # Set frame rate to 30fps
            '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',  # AAC audio
            '-movflags', '+faststart',  # Fast start for streaming
            output_file
        ])
        print(f"Preprocessing complete: {output_file}")
    except Exception as e:
        print(f"Error preprocessing file {input_file}: {e}")


def download_and_preprocess_videos(videos, download_path):
    # Define the archive file path in the same folder as the downloaded videos
    archive_path = os.path.join(download_path, "archive.txt")

    total_videos = len(videos)
    processed_videos = 0

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

        # Print running number and video count
        print(f"Downloading {index}/{total_videos}: {video_title}")

        # Use yt-dlp to download the video
        yt_dlp_command = (
            f'yt-dlp --download-archive "{archive_path}" '
            f'-o "{output_template}.%(ext)s" https://www.youtube.com/watch?v={video_id}'
        )
        download_result = os.system(yt_dlp_command)

        # Check if the video was actually downloaded
        if os.path.exists(downloaded_file):
            print(f"Downloaded {video_title} as {downloaded_file}")
            # Preprocess the downloaded file
            preprocess_file(downloaded_file, processed_file)

            # Remove the original file after preprocessing
            if os.path.exists(downloaded_file):
                os.remove(downloaded_file)
                print(f"Original file deleted: {downloaded_file}")

            # Increment the processed video count and show progress
            processed_videos += 1
            print(f"Progress: {processed_videos}/{total_videos} videos processed.")
        else:
            # If the video was skipped, move on to the next one
            print(f"Video {video_title} was skipped (already in archive). Skipping ffmpeg processing.")


def main():
    # Load videos from the JSON file
    videos = load_videos_from_json()

    # Define the date range (hardcoded)
    start_date = "2023-01-30"  # Set start date here
    end_date = "2024-01-01"  # Set end date here

    # Define the download path
    download_path = r"E:\Niilo22\2023"  # Set your download path here

    # Ensure the download path exists, create if not
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    # Filter videos by the date range provided in the code
    filtered_videos = filter_videos_by_date(videos, start_date, end_date)

    # Print how many videos will be downloaded
    video_count = len(filtered_videos)
    if video_count == 0:
        print(f"No videos found between {start_date} and {end_date}.")
        return
    else:
        print(f"{video_count} videos will be downloaded from {start_date} to {end_date}.")

    # Download and preprocess the videos
    download_and_preprocess_videos(filtered_videos, download_path)

    # Print a success message
    print(f"Downloaded and preprocessed videos from {start_date} to {end_date} to {download_path}.")


if __name__ == "__main__":
    main()

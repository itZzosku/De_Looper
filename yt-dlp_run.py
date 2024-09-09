import json
from datetime import datetime
import os


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


def download_videos(videos, download_path):
    # Define the archive file path in the same folder as the downloaded videos
    archive_path = os.path.join(download_path, "archive.txt")

    total_videos = len(videos)

    # Download each video using yt-dlp with a specified download path and custom file name
    for index, video in enumerate(videos, start=1):
        video_id = video['id']
        video_title = video['name']
        published_at = video['publishedAt']

        # Generate the timestamp and date string
        unix_timestamp = get_unix_timestamp(published_at)
        date_string = get_date_string(published_at)

        # Create the custom file name: "timestamp_date_video_title.ext"
        output_template = f"{download_path}/{unix_timestamp}_{date_string}_{video_title}"

        # Print running number and video count
        print(f"Downloading {index}/{total_videos}: {video_title}")

        # Use yt-dlp with the custom output template and archive file
        os.system(f'yt-dlp --download-archive "{archive_path}" -o "{output_template}.%(ext)s" https://www.youtube.com/watch?v={video_id}')
        print(f"Downloaded {video_title} as {output_template}")


def main():
    # Load videos from the JSON file
    videos = load_videos_from_json()

    # Define the date range (hardcoded)
    start_date = "2024-01-01"  # Set start date here
    end_date = "2025-01-01"  # Set end date here

    # Define the download path
    download_path = r"E:\Niilo22\2024"  # Set your download path here

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

    # Download the filtered videos using yt-dlp
    download_videos(filtered_videos, download_path)

    # Print a success message
    print(f"Downloaded videos from {start_date} to {end_date} to {download_path}.")


if __name__ == "__main__":
    main()

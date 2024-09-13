import json
import os
import re
from datetime import datetime
import ytdlp_prerun  # Import the module with the new name


def load_videos_from_json(filename='videos.json'):
    with open(filename, 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)
    videos = data.get('videos', [])
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


def check_existing_file(video_title, download_path):
    for file in os.listdir(download_path):
        if file.endswith(".mp4"):
            # Extract the part of the filename that contains the video title
            file_title = file.split('_', 2)[-1].rsplit('_', 1)[0]
            if file_title == video_title:
                return os.path.join(download_path, file)  # Return the full path if a match is found
    return None


def download_videos(videos, download_path):
    # Define the archive file path in the same folder as the downloaded videos
    archive_path = os.path.join(download_path, "archive.txt")

    total_videos = len(videos)

    # Download each video using yt-dlp with a specified download path and custom file name
    for index, video in enumerate(videos, start=1):
        video_id = video['id']
        video_title = sanitize_filename(video['name'])  # Sanitize the video title to avoid file naming issues
        published_at = video['publishedAt']

        # Generate the timestamp and date string
        unix_timestamp = get_unix_timestamp(published_at)
        date_string = get_date_string(published_at)

        # Create the custom file name: "timestamp_date_video_title.ext"
        output_template = f"{download_path}/{unix_timestamp}_{date_string}_{video_title}"

        # Check if the video has already been downloaded or processed by comparing video titles
        existing_file = check_existing_file(video_title, download_path)
        if existing_file:
            print(f"File already exists: {existing_file}. Skipping download.")
            continue

        # Print running number and video count
        print(f"Downloading {index}/{total_videos}: {video_title}")

        # Use yt-dlp with the custom output template and archive file
        os.system(
            f'yt-dlp --download-archive "{archive_path}" -o "{output_template}.%(ext)s" https://www.youtube.com/watch?v={video_id}'
        )
        print(f"Downloaded {video_title} as {output_template}")


def main():
    # Call the function from the imported module
    ytdlp_prerun.check_and_update_videos_json()

    # Now load videos from the JSON file
    videos = load_videos_from_json()

    # Take user input for date range and download path
    start_date = input("Enter the start date (YYYY-MM-DD): ")
    end_date = input("Enter the end date (YYYY-MM-DD): ")
    download_path = input("Enter the download path: ")

    # Ensure the download path exists, create if not
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    # Filter videos by the date range provided
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

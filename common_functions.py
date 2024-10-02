from datetime import datetime
import json
import os
from functools import lru_cache

# Define problematic characters and create a reusable translation table
problematic_chars = '\\/:\"*?<>|'
translation_table = str.maketrans({char: '-' for char in problematic_chars})
PROCESSED_SUFFIX = '_processed.mp4'


def sanitize_filename(title):
    """
    Sanitize file names by replacing problematic characters and normalizing whitespace.
    """
    # Replace problematic characters using translate
    sanitized = title.translate(translation_table)
    # Normalize whitespace by splitting and rejoining
    sanitized = ' '.join(sanitized.split()).rstrip('_')
    return sanitized


def get_unix_timestamp_and_date_string(published_at):
    """
    Parse the publishedAt string into both a Unix timestamp and a date string (YYYYMMDD).

    Args:
        published_at (str): Date and time in string format ('%Y-%m-%dT%H:%M:%SZ').

    Returns:
        tuple: (Unix timestamp, Date string in YYYYMMDD format).
    """
    # Convert publishedAt string to Unix timestamp and date string (YYYYMMDD)
    dt = datetime.strptime(published_at, '%Y-%m-%dT%H:%M:%SZ')
    unix_timestamp = int(dt.timestamp())
    date_string = dt.strftime('%Y%m%d')
    return unix_timestamp, date_string


def load_videos_json(videos_json_path='videos.json'):
    """
    Load video data from a JSON file with error handling.

    Args:
        videos_json_path (str): Path to the JSON file. Defaults to 'videos.json'.

    Returns:
        list: A list of videos, or an empty list if an error occurs.
    """
    try:
        with open(videos_json_path, 'r', encoding='utf-8') as json_file:
            videos_data = json.load(json_file)

        # Check if 'videos' key exists and is a list
        if 'videos' in videos_data and isinstance(videos_data['videos'], list):
            return videos_data['videos']  # Return the list of videos
        else:
            print(f"Error: 'videos' key not found or is not a list in {videos_json_path}")
            return []

    except json.JSONDecodeError as e:
        print(f"JSON decoding error in {videos_json_path}: {e}")
        return []

    except FileNotFoundError:
        print(f"File {videos_json_path} not found.")
        return []

    except Exception as e:
        print(f"Error loading {videos_json_path}: {e}")
        return []


def check_existing_file(video_title, download_path):
    """
    Check if a video with the given title has already been downloaded or processed in the download path.

    Args:
        video_title (str): Title of the video.
        download_path (str): Path where the videos are downloaded.

    Returns:
        str: The full path of the existing file if found, otherwise None.
    """
    # Sanitize the video title to match how filenames are sanitized
    sanitized_video_title = sanitize_filename(video_title)

    for file in os.listdir(download_path):
        if file.endswith('.mp4'):
            # Remove the file extension and the '_processed' suffix if present
            if file.endswith('_processed.mp4'):
                base_filename = file[:-len('_processed.mp4')]
            else:
                base_filename = file[:-len('.mp4')]

            # Extract the video title part
            parts = base_filename.split('_', 2)
            if len(parts) >= 3:
                file_title = parts[2]  # This includes the rest of the filename (video title)
                # Sanitize the file title to ensure consistent comparison
                sanitized_file_title = sanitize_filename(file_title)

                if sanitized_file_title == sanitized_video_title:
                    return os.path.join(download_path, file)  # Return the full path if a match is found
    return None


@lru_cache(None)  # Cache results for repeated strptime calls to optimize performance
def parse_date(date_string):
    """
    Parse a date string into a datetime object.

    Args:
        date_string (str): Date and time in string format ('%Y-%m-%dT%H:%M:%SZ').

    Returns:
        datetime: Parsed datetime object.
    """
    return datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%SZ')


def filter_videos_by_date(videos, start_date, end_date):
    """
    Filter a list of videos by the given start and end date.

    Args:
        videos (list): List of video objects containing the 'publishedAt' key.
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.

    Returns:
        list: Filtered list of videos within the date range.
    """
    # Convert string dates to datetime objects
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')

    # Filter videos by date range
    filtered_videos = [
        video for video in videos
        if start_date <= parse_date(video['publishedAt']) <= end_date
    ]

    return filtered_videos

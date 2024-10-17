import os
import json
import argparse
import datetime
import subprocess
from common_functions import sanitize_filename, load_videos_json


def extract_video_title_from_filename(filename):
    """
    Extracts the video title from the filename.
    Assumes the filename is in the format: "{timestamp}_{date}_{video_title}[_processed].mp4"
    """
    basename = os.path.basename(filename)
    if basename.endswith('_processed.mp4'):
        basename = basename[:-len('_processed.mp4')]
    elif basename.endswith('.mp4'):
        basename = basename[:-len('.mp4')]
    else:
        return None  # Not a video file we are interested in

    # Split the basename by underscores
    parts = basename.split('_')
    if len(parts) < 3:
        return None  # Filename does not match expected format

    # The video title is the remaining parts after removing timestamp and date
    video_title = '_'.join(parts[2:])
    return video_title


def is_video_playable(filepath):
    """
    Checks if a video file is playable using ffprobe.
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
             "stream=codec_type", "-of", "default=noprint_wrappers=1", filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        # If ffprobe outputs stream information, the video is playable
        return bool(result.stdout.strip())
    except Exception as e:
        print(f"Error checking playability for {filepath}: {e}")
        return False


def get_video_duration(filepath):
    """
    Gets the duration of a video file using ffprobe.
    """
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        duration_str = result.stdout.strip()
        if duration_str:
            return float(duration_str)
        else:
            print(f"ffprobe did not return duration for {filepath}")
            return None
    except Exception as e:
        print(f"Error getting duration for {filepath}: {e}")
        return None


def get_video_titles_in_directory(directory):
    """
    Returns two sets:
    - downloaded_titles: video titles from downloaded video files (.mp4 without '_processed')
    - preprocessed_titles: video titles from preprocessed video files (ending with '_processed.mp4')
    """
    downloaded_titles = set()
    preprocessed_titles = set()
    for filename in os.listdir(directory):
        if filename.endswith('.mp4'):
            video_title = extract_video_title_from_filename(filename)
            if video_title:
                sanitized_title = sanitize_filename(video_title)
                if filename.endswith('_processed.mp4'):
                    preprocessed_titles.add(sanitized_title)
                else:
                    downloaded_titles.add(sanitized_title)
    return downloaded_titles, preprocessed_titles


def compare_videos_with_directory(videos, directory, year, duration_cache):
    """
    Compares the videos from videos.json for a specific year with the videos in the directory.
    Reports statistics and any videos that are missing or need preprocessing.
    Also checks if videos are playable, obtains their durations, and updates the duration_cache.
    """
    expected_titles = set()
    for video in videos:
        published_at = video['publishedAt']
        video_year = datetime.datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").year
        if video_year == year:
            video_title = sanitize_filename(video['name'])
            expected_titles.add(video_title)

    total_expected = len(expected_titles)
    if total_expected == 0:
        print(f"No videos found in videos.json for the year {year}.")
        return

    downloaded_titles, preprocessed_titles = get_video_titles_in_directory(directory)

    missing_titles = expected_titles - (downloaded_titles | preprocessed_titles)
    downloaded_only = downloaded_titles - preprocessed_titles
    preprocessed_only = preprocessed_titles

    total_downloaded = len(downloaded_titles | preprocessed_titles)
    total_preprocessed = len(preprocessed_titles)

    print(f"\nYear: {year}")
    print(f"Directory: {directory}")
    print(f"Total videos expected: {total_expected}")
    print(f"Total videos downloaded: {total_downloaded}")
    print(f"Total videos preprocessed: {total_preprocessed}")
    print(f"Total videos missing: {len(missing_titles)}")
    print(f"Total videos downloaded but not preprocessed: {len(downloaded_only)}")

    if missing_titles:
        print(f"\nThe following {len(missing_titles)} videos are missing or not downloaded:")
        for title in sorted(missing_titles):
            print(f"- {title}")

    if downloaded_only:
        print(f"\nThe following {len(downloaded_only)} videos are downloaded but not preprocessed:")
        for title in sorted(downloaded_only):
            print(f"- {title}")

    # Now check playability and durations
    for filename in os.listdir(directory):
        if filename.endswith('.mp4'):
            file_path = os.path.join(directory, filename)
            video_title = extract_video_title_from_filename(filename)
            if video_title:
                sanitized_title = sanitize_filename(video_title)
                # Only process videos that are in expected titles
                if sanitized_title in expected_titles:
                    # Check if duration is already in cache
                    if filename in duration_cache:
                        # print(f"Duration already cached for {filename}. Skipping processing this video.")
                        continue  # Skip processing this video
                    else:
                        # Check if the video is playable
                        if is_video_playable(file_path):
                            print(f"Video {filename} is playable.")
                            duration = get_video_duration(file_path)
                            if duration is not None:
                                # Update the cache
                                duration_cache[filename] = duration
                                print(f"Duration for {filename}: {duration} seconds")
                            else:
                                print(f"Could not obtain duration for {filename}.")
                        else:
                            print(f"Video {filename} is not playable.")
                            # Optionally, mark this in the cache or take other actions

    if not missing_titles and not downloaded_only:
        print("\nAll expected videos for the year are downloaded and preprocessed.")


def main():
    # Load videos from videos.json
    videos = load_videos_json()

    # Set up argument parser
    parser = argparse.ArgumentParser(description='Compare videos with directory')
    parser.add_argument('--folder', required=True, help='Directory containing video files or directories per year')
    parser.add_argument('--year', type=int,
                        help='Year to check (e.g., 2022). If not provided, all year subdirectories will be checked.')
    args = parser.parse_args()

    directory = args.folder
    year = args.year

    # Ensure the directory exists
    if not os.path.isdir(directory):
        print(f"Error: The directory '{directory}' does not exist.")
        return

    # Load duration cache
    script_dir = os.path.dirname(os.path.abspath(__file__))
    duration_cache_path = os.path.join(script_dir, "duration_cache.json")
    duration_cache = {}
    if os.path.exists(duration_cache_path):
        try:
            with open(duration_cache_path, 'r', encoding='utf-8') as cache_file:
                duration_cache = json.load(cache_file)
        except json.JSONDecodeError:
            print(
                f"Warning: The duration cache file '{duration_cache_path}' is empty or invalid. It will be recreated.")
            duration_cache = {}
    else:
        duration_cache = {}

    if year:
        # If year is specified, check only that year in the given directory
        year_directory = directory
        if not os.path.isdir(year_directory):
            print(f"Error: The directory '{year_directory}' does not exist.")
            return
        # Compare the videos with the directory
        compare_videos_with_directory(videos, year_directory, year, duration_cache)
    else:
        # If year is not specified, iterate through subdirectories and process each year
        for subdir in os.listdir(directory):
            subdir_path = os.path.join(directory, subdir)
            if os.path.isdir(subdir_path) and subdir.isdigit():
                year = int(subdir)
                compare_videos_with_directory(videos, subdir_path, year, duration_cache)
            else:
                # Skip non-numeric subdirectories
                continue

    # Save updated duration cache with sorted keys for better readability
    with open(duration_cache_path, 'w', encoding='utf-8') as cache_file:
        json.dump(duration_cache, cache_file, indent=4, ensure_ascii=False, sort_keys=True)
    print(f"\nUpdated duration cache saved to {duration_cache_path}")


if __name__ == "__main__":
    main()

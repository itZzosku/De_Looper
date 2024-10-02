import os
import json
import subprocess
from datetime import datetime
import argparse
import ytdlp_prerun  # Import the ytdlp_prerun module
from common_functions import sanitize_filename
from common_functions import load_videos_json
from urllib.parse import urlparse, urlunparse


def get_video_duration(filepath):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration for {filepath}: {e}")
        return 0


def format_duration(total_seconds):
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    return f"{hours}h {minutes}m {seconds}s"


def extract_video_name_and_date(filename):
    try:
        # Split the filename by '_'
        parts = filename.split('_')
        # Ensure there are enough parts
        if len(parts) >= 3:
            # The video name is the third part onwards
            video_name_with_extension = '_'.join(parts[2:])
            # Remove '_processed.mp4' or '.mp4' suffix
            if video_name_with_extension.endswith('_processed.mp4'):
                video_name = video_name_with_extension[:-13]  # Remove '_processed.mp4'
            else:
                video_name = os.path.splitext(video_name_with_extension)[0]
            # Strip any trailing underscores
            video_name = video_name.rstrip('_')
            # Extract the date part
            date_str = parts[1]  # e.g., '20130101'
            # Convert date_str to 'YYYY-MM-DD' format
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            video_date = date_obj.strftime('%Y-%m-%d')
            return video_name, video_date
        else:
            return "Unknown Title", None
    except Exception as e:
        print(f"Error extracting video name and date from {filename}: {e}")
        return "Unknown Title", None


def build_video_lookup(videos_list):
    video_lookup = {}
    duplicates = {}
    for video in videos_list:
        original_video_name = video.get('name')
        published_at = video.get('publishedAt')
        video_number = video.get('videoNumber')

        if original_video_name is None or published_at is None or video_number is None:
            continue

        sanitized_name = sanitize_filename(original_video_name)
        published_date = published_at.split('T')[0]  # 'YYYY-MM-DD'

        key = (sanitized_name, published_date)

        if key in video_lookup:
            # Handle duplicates by tracking them
            if key not in duplicates:
                duplicates[key] = [video_lookup[key]]
            duplicates[key].append(video_number)
        else:
            video_lookup[key] = video_number

    # Handle duplicates
    for key, video_numbers in duplicates.items():
        sanitized_name, published_date = key
        print(f"Multiple videos found for '{sanitized_name}' on date {published_date}. Skipping these entries.")
        for video_number in video_numbers:
            video_lookup.pop(key, None)  # Remove duplicates

    return video_lookup


def find_video_number(video_lookup, sanitized_video_name, video_date):
    return video_lookup.get((sanitized_video_name, video_date), None)


def commit_and_push_changes(git_username, git_token, script_dir, new_videos_count):
    try:
        # Check if duration_cache.json has uncommitted changes
        git_status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=script_dir,
            stdout=subprocess.PIPE, text=True
        )
        if "duration_cache.json" in git_status_result.stdout:
            print("New videos have been added to duration_cache.json. Committing and pushing to git...")

            # Add duration_cache.json
            subprocess.run(["git", "add", "duration_cache.json"], cwd=script_dir, check=True)

            # Commit with a message including the number of new videos
            commit_message = f"Added durations for {new_videos_count} new videos to duration_cache.json"
            subprocess.run(["git", "commit", "-m", commit_message], cwd=script_dir, check=True)

            # Get the remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=script_dir,
                stdout=subprocess.PIPE, text=True
            )
            git_remote_url = result.stdout.strip()

            # Parse the URL
            parsed_url = urlparse(git_remote_url)

            # Construct the URL with credentials
            if parsed_url.scheme == 'https':
                netloc = f"{git_username}:{git_token}@{parsed_url.netloc}"
                git_remote_with_credentials = parsed_url._replace(netloc=netloc).geturl()
                # Push
                push_result = subprocess.run(
                    ["git", "push", git_remote_with_credentials],
                    cwd=script_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if push_result.returncode == 0:
                    print("Changes have been pushed to git successfully.")
                else:
                    print("Error pushing changes to git. Please check your git settings and try again.")
            else:
                print("Only HTTPS remote URLs are supported for automatic pushing with username and token.")
        else:
            print("No changes to duration_cache.json to commit.")
    except Exception as e:
        print(f"An error occurred while committing and pushing changes: {e}")


def main():
    # Step 1: Update videos.json by running ytdlp_prerun.py
    print("Updating videos.json by fetching latest videos from YouTube...")
    try:
        ytdlp_prerun.check_and_update_videos_json()
        print("videos.json has been updated successfully.")
    except Exception as e:
        print(f"Error updating videos.json: {e}")
        print("Exiting the playlist generator.")
        return

    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Generate a playlist JSON from video files.")
    parser.add_argument(
        '--video_folders', nargs='*', help="Paths to your video folders, separated by spaces."
    )
    parser.add_argument(
        '--path_style', choices=['1', '2'], help="Path style: 1 for Windows, 2 for Linux."
    )
    args = parser.parse_args()

    # If arguments are not provided, prompt the user for input
    if not args.video_folders:
        video_folders_input = input("Enter the paths to your video folders, separated by commas: ")
        video_folders = video_folders_input.split(',')
    else:
        video_folders = args.video_folders

    if not args.path_style:
        path_style = input("Choose path style (1 for Windows, 2 for Linux): ")
    else:
        path_style = args.path_style

    # Apply the correct path style
    if path_style == "1":
        video_folders = [folder.strip().replace("/", "\\") for folder in video_folders]
    elif path_style == "2":
        video_folders = [folder.strip().replace("\\", "/") for folder in video_folders]
    else:
        print("Invalid choice. Using default path style (Linux).")
        video_folders = [folder.strip().replace("\\", "/") for folder in video_folders]

    # Output JSON will be saved in the same folder as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_json = os.path.join(script_dir, "playlist.json")
    videos_json_path = os.path.join(script_dir, "videos.json")

    # Load config.json
    config_json_path = os.path.join(script_dir, "config.json")
    try:
        with open(config_json_path, 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
            git_username = config.get("git_username")
            git_token = config.get("git_token")
            if not git_username or not git_token:
                print("git_username or git_token is missing in config.json. Exiting.")
                return
    except Exception as e:
        print(f"Error loading config.json: {e}")
        print("Exiting the playlist generator.")
        return

    # Load duration cache
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

    # Load videos.json
    videos_list = load_videos_json(videos_json_path)
    if videos_list is None:
        print("Failed to load videos.json. Exiting.")
        return

    # Build the lookup dictionary
    video_lookup = build_video_lookup(videos_list)

    # Initialize variables
    playlist = {
        "playlist": []
    }
    total_duration = 0

    # Counter for new videos added to duration_cache
    new_videos_count = 0

    # Process video files
    for video_folder in video_folders:
        if not os.path.isdir(video_folder):
            print(f"Video folder '{video_folder}' does not exist or is not a directory. Skipping.")
            continue

        video_files = sorted([f for f in os.listdir(video_folder) if f.endswith('.mp4')])

        for video_file in video_files:
            file_path = os.path.join(video_folder, video_file)

            # Use cached duration if available
            if video_file in duration_cache:
                duration = duration_cache[video_file]
            else:
                duration = get_video_duration(file_path)
                # Update the cache
                duration_cache[video_file] = duration
                # Increment new videos count
                new_videos_count += 1

            total_duration += duration  # Add each clip's duration to total

            # Extract video name and date from the filename
            video_name, video_date = extract_video_name_and_date(video_file)
            if video_date is None:
                print(f"Could not extract date from filename '{video_file}'. Skipping.")
                continue
            sanitized_video_name = sanitize_filename(video_name)

            # Find the videoNumber using the lookup dictionary
            video_number = find_video_number(video_lookup, sanitized_video_name, video_date)
            if video_number is None:
                print(f"No matching videoNumber found for '{video_name}' on date {video_date}. Skipping.")
                continue

            entry = {
                "videoNumber": video_number,
                "name": video_name,
                "file_path": file_path,
                "duration": duration,
                "release_date": video_date,
                # You can include other fields if needed
            }
            playlist["playlist"].append(entry)

            # Print progress
            print(f"Processed videoNumber {video_number}: {video_file}")

    # Update total_duration in the playlist
    playlist["total_duration"] = format_duration(total_duration)

    # Write the JSON to the output file with UTF-8 encoding and ensure_ascii=False
    with open(output_json, 'w', encoding='utf-8') as json_file:
        json.dump(playlist, json_file, indent=4, ensure_ascii=False)

    # Save updated duration cache with sorted keys for better readability
    with open(duration_cache_path, 'w', encoding='utf-8') as cache_file:
        json.dump(duration_cache, cache_file, indent=4, ensure_ascii=False, sort_keys=True)

    print(f"Playlist saved to {output_json}")
    print(f"Total playlist duration: {format_duration(total_duration)}")

    # Commit and push changes to git if duration_cache.json has been updated
    commit_and_push_changes(git_username, git_token, script_dir, new_videos_count)


if __name__ == "__main__":
    main()

import os
import re
import json
import subprocess
from datetime import datetime
import argparse


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


def sanitize_filename(title):
    # Replace problematic characters (e.g., slashes, colons, etc.) with hyphens
    sanitized = re.sub(r'[\\/:"*?<>|]', '-', title)
    # Normalize whitespace and remove trailing underscores
    sanitized = re.sub(r'\s+', ' ', sanitized).strip().rstrip('_')
    return sanitized


def load_videos_json(videos_json_path):
    try:
        with open(videos_json_path, 'r', encoding='utf-8') as json_file:
            videos_data = json.load(json_file)
        # Check if 'videos' key exists
        if 'videos' in videos_data and isinstance(videos_data['videos'], list):
            return videos_data['videos']  # Return the list of videos
        else:
            print(f"Error: 'videos' key not found or is not a list in {videos_json_path}")
            return None
    except json.JSONDecodeError as e:
        print(f"JSON decoding error in {videos_json_path}: {e}")
        return None
    except Exception as e:
        print(f"Error loading {videos_json_path}: {e}")
        return None


def find_video_number(videos_list, sanitized_video_name, video_date):
    matches = []
    for video in videos_list:
        original_video_name = video.get('name')
        if original_video_name is None:
            continue
        sanitized_name_in_json = sanitize_filename(original_video_name)
        # Extract date from 'publishedAt'
        published_at = video.get('publishedAt')
        if published_at:
            published_date = published_at.split('T')[0]  # 'YYYY-MM-DD'
        else:
            continue
        if sanitized_name_in_json == sanitized_video_name and published_date == video_date:
            matches.append(video)

    if len(matches) == 1:
        return matches[0].get('videoNumber')
    elif len(matches) > 1:
        print(f"Multiple videos found for '{sanitized_video_name}' on date {video_date}. Skipping.")
        return None
    else:
        return None


def main():
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

    # Load duration cache
    duration_cache_path = os.path.join(script_dir, "duration_cache.json")
    if os.path.exists(duration_cache_path):
        with open(duration_cache_path, 'r', encoding='utf-8') as cache_file:
            duration_cache = json.load(cache_file)
    else:
        duration_cache = {}

    # Load videos.json
    videos_list = load_videos_json(videos_json_path)
    if videos_list is None:
        print("Failed to load videos.json. Exiting.")
        return

    # Initialize variables
    playlist = {
        "playlist": []
    }
    total_duration = 0

    # Process video files
    for video_folder in video_folders:
        video_files = sorted([f for f in os.listdir(video_folder) if f.endswith('.mp4')])

        for video_file in video_files:
            file_path = os.path.join(video_folder, video_file)

            # Use cached duration if available
            if file_path in duration_cache:
                duration = duration_cache[file_path]
            else:
                duration = get_video_duration(file_path)
                # Update the cache
                duration_cache[file_path] = duration

            total_duration += duration  # Add each clip's duration to total

            # Extract video name and date from the filename
            video_name, video_date = extract_video_name_and_date(video_file)
            if video_date is None:
                print(f"Could not extract date from filename '{video_file}'. Skipping.")
                continue
            sanitized_video_name = sanitize_filename(video_name)

            # Find the videoNumber from videos.json
            video_number = find_video_number(videos_list, sanitized_video_name, video_date)
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
        json.dump(playlist, json_file, indent=2, ensure_ascii=False)

    # Save updated duration cache
    with open(duration_cache_path, 'w', encoding='utf-8') as cache_file:
        json.dump(duration_cache, cache_file)

    print(f"Playlist saved to {output_json}")
    print(f"Total playlist duration: {format_duration(total_duration)}")


if __name__ == "__main__":
    main()

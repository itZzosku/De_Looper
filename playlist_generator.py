import os
import json
import subprocess
from datetime import datetime, timezone
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


def extract_release_data(filename):
    try:
        timestamp_str = filename.split('_')[0]
        timestamp = int(timestamp_str)
        release_datetime = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        release_date = release_datetime.strftime("%Y-%m-%d")
        release_time = release_datetime.strftime("%H:%M:%S")
        return release_date, release_time
    except Exception as e:
        print(f"Error extracting release data from {filename}: {e}")
        return "1970-01-01", "00:00:00"


def extract_video_name(filename):
    try:
        name_part = filename.split('_', 3)
        if len(name_part) > 2:
            return name_part[2].split('_')[0].replace('.mp4', '')
        else:
            return "Unknown Title"
    except Exception as e:
        print(f"Error extracting video name from {filename}: {e}")
        return "Unknown Title"


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

    # Create the JSON structure with 'playlist'
    playlist = {
        "playlist": []
    }

    # Initialize a variable to hold the total duration in seconds
    total_duration = 0
    file_id = 1  # Start file ID from 1

    # Go through each folder in the list
    for video_folder in video_folders:
        # List all video files in the current folder
        video_files = sorted([f for f in os.listdir(video_folder) if f.endswith('.mp4')])

        # Scan the folder for video files and generate playlist entries
        for index, video_file in enumerate(video_files):
            file_path = os.path.join(video_folder, video_file)
            duration = get_video_duration(file_path)
            total_duration += duration  # Add each clip's duration to total

            # Extract release date, time, and video name from the filename
            release_date, release_time = extract_release_data(video_file)
            video_name = extract_video_name(video_file)

            entry = {
                "id": file_id,  # Use a global file_id for unique IDs
                "name": video_name,
                "file_path": file_path,
                "duration": duration,
                "release_date": release_date,
                "release_time": release_time
            }
            playlist["playlist"].append(entry)

            # Print progress
            print(f"Processing file {file_id}: {video_file}")

            file_id += 1  # Increment the file ID after each file

    # Add total video duration in hours, minutes, and seconds to the playlist
    playlist["total_duration"] = format_duration(total_duration)

    # Write the JSON to the output file with UTF-8 encoding and ensure_ascii=False
    with open(output_json, 'w', encoding='utf-8') as json_file:
        json.dump(playlist, json_file, indent=2, ensure_ascii=False)

    print(f"Playlist saved to {output_json}")
    print(f"Total playlist duration: {format_duration(total_duration)}")


if __name__ == "__main__":
    main()

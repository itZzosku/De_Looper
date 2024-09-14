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

    # Initialize variables
    playlist = {
        "playlist": []
    }
    total_duration = 0
    file_id = 1  # Start file ID from 1

    # Check if playlist.json exists
    if os.path.exists(output_json):
        try:
            with open(output_json, 'r', encoding='utf-8') as json_file:
                existing_data = json.load(json_file)

            # Build a set of existing file paths from the playlist
            existing_file_paths = set(entry['file_path'] for entry in existing_data.get('playlist', []))

            # Build a set of current file paths from the video folders
            current_file_paths = set()
            for video_folder in video_folders:
                video_files = [f for f in os.listdir(video_folder) if f.endswith('.mp4')]
                for video_file in video_files:
                    file_path = os.path.join(video_folder, video_file)
                    current_file_paths.add(file_path)

            # Check for missing files
            missing_files = existing_file_paths - current_file_paths
            new_files = current_file_paths - existing_file_paths

            if missing_files:
                print("Some files in playlist.json are missing from the folders.")
                print("Regenerating playlist.json from scratch.")
                regenerate_playlist = True
            else:
                print("No missing files detected. Updating playlist.json with new videos.")
                regenerate_playlist = False
                # Load existing playlist
                playlist = existing_data
                # Calculate total duration from existing entries
                total_duration = sum(entry['duration'] for entry in playlist.get('playlist', []))
                # Update file_id to continue from the last ID
                if playlist['playlist']:
                    file_id = max(entry['id'] for entry in playlist['playlist']) + 1
                else:
                    file_id = 1
        except Exception as e:
            print(f"Error reading existing playlist.json: {e}")
            print("Regenerating playlist.json from scratch.")
            regenerate_playlist = True
    else:
        print("playlist.json does not exist. Creating a new one.")
        regenerate_playlist = True

    if regenerate_playlist:
        # Start fresh
        playlist = {
            "playlist": []
        }
        total_duration = 0
        file_id = 1
        new_files = set()  # Process all files as new

        # Build a set of current file paths from the video folders
        for video_folder in video_folders:
            video_files = [f for f in os.listdir(video_folder) if f.endswith('.mp4')]
            for video_file in video_files:
                file_path = os.path.join(video_folder, video_file)
                new_files.add(file_path)

    # Process new files
    for video_folder in video_folders:
        video_files = sorted([f for f in os.listdir(video_folder) if f.endswith('.mp4')])

        for video_file in video_files:
            file_path = os.path.join(video_folder, video_file)

            if file_path in new_files:
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
                print(f"Processing new file {file_id}: {video_file}")

                file_id += 1  # Increment the file ID after each file

    # Update total_duration in the playlist
    if not regenerate_playlist:
        # If appending, recalculate total_duration
        total_duration = sum(entry['duration'] for entry in playlist.get('playlist', []))
    playlist["total_duration"] = format_duration(total_duration)

    # Write the JSON to the output file with UTF-8 encoding and ensure_ascii=False
    with open(output_json, 'w', encoding='utf-8') as json_file:
        json.dump(playlist, json_file, indent=2, ensure_ascii=False)

    print(f"Playlist saved to {output_json}")
    print(f"Total playlist duration: {format_duration(total_duration)}")


if __name__ == "__main__":
    main()

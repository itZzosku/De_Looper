import os
import json
import subprocess
from datetime import datetime, timezone

# Ask for the video folder as input
video_folder = input("Enter the path to your video folder: ")

# Ask whether to use Windows or Linux-style paths
path_style = input("Choose path style (1 for Windows, 2 for Linux): ")

if path_style == "1":
    # If Windows, use double backslashes
    video_folder = video_folder.replace("/", "\\")
elif path_style == "2":
    # If Linux, use single forward slashes
    video_folder = video_folder.replace("\\", "/")
else:
    print("Invalid choice. Using default path style (Linux).")
    video_folder = video_folder.replace("\\", "/")

# Output JSON will be saved in the same folder as this script
script_dir = os.path.dirname(os.path.abspath(__file__))
output_json = os.path.join(script_dir, "playlist.json")


# Function to get video duration using ffprobe
def get_video_duration(filepath):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
             filepath],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration for {filepath}: {e}")
        return 0


# Function to convert seconds to hours, minutes, and seconds
def format_duration(total_seconds):
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    return f"{hours}h {minutes}m {seconds}s"


# Function to extract Unix timestamp from filename and convert to release date and time
def extract_release_data(filename):
    try:
        # Extract Unix timestamp
        timestamp_str = filename.split('_')[0]  # Gets the first part of the filename as the Unix timestamp
        timestamp = int(timestamp_str)

        # Use timezone-aware datetime for UTC
        release_datetime = datetime.fromtimestamp(timestamp, tz=timezone.utc)

        release_date = release_datetime.strftime("%Y-%m-%d")
        release_time = release_datetime.strftime("%H:%M:%S")

        return release_date, release_time
    except Exception as e:
        print(f"Error extracting release data from {filename}: {e}")
        return "1970-01-01", "00:00:00"  # Default fallback values


# Function to extract the video name from filename
def extract_video_name(filename):
    try:
        name_part = filename.split('_', 2)[2]  # Get the part after the second underscore
        return name_part.replace('.mp4', '')  # Remove the .mp4 extension
    except Exception as e:
        print(f"Error extracting video name from {filename}: {e}")
        return "Unknown Title"


# Create the JSON structure with 'playlist'
playlist = {
    "playlist": []
}

# List of all video files
video_files = sorted([f for f in os.listdir(video_folder) if f.endswith('.mp4')])

# Total number of files
total_files = len(video_files)

# Initialize a variable to hold the total duration in seconds
total_duration = 0

# Scan the folder for video files and generate playlist entries
for index, video_file in enumerate(video_files):
    file_path = os.path.join(video_folder, video_file)
    duration = get_video_duration(file_path)
    total_duration += duration  # Add each clip's duration to total

    # Extract release date, time, and video name from the filename
    release_date, release_time = extract_release_data(video_file)
    video_name = extract_video_name(video_file)

    entry = {
        "id": index + 1,  # Assuming index + 1 is the id
        "name": video_name,
        "file_path": file_path,
        "duration": duration,
        "release_date": release_date,
        "release_time": release_time
    }
    playlist["playlist"].append(entry)

    # Print progress
    print(f"Processing file {index + 1}/{total_files}: {video_file}")

# Add total video duration in hours, minutes, and seconds to the playlist
playlist["total_duration"] = format_duration(total_duration)

# Write the JSON to the output file with UTF-8 encoding and ensure_ascii=False
with open(output_json, 'w', encoding='utf-8') as json_file:
    json.dump(playlist, json_file, indent=2, ensure_ascii=False)

print(f"Playlist saved to {output_json}")
print(f"Total playlist duration: {format_duration(total_duration)}")

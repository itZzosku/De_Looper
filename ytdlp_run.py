import os
import subprocess
import argparse
import ytdlp_prerun  # Import the module that checks and updates videos.json
from concurrent.futures import ThreadPoolExecutor, as_completed
from common_functions import sanitize_filename
from common_functions import get_unix_timestamp_and_date_string  # Updated to use the combined function
from common_functions import load_videos_json  # Using the updated load_videos_json
from common_functions import check_existing_file
from common_functions import filter_videos_by_date


def download_video(video, download_path, archive_path):
    video_id = video['id']
    video_title = sanitize_filename(video['name'])  # Sanitize the video title to avoid file naming issues
    published_at = video['publishedAt']

    # Generate the Unix timestamp and date string
    unix_timestamp, date_string = get_unix_timestamp_and_date_string(published_at)

    # Create the custom file name: "timestamp_date_video_title.ext"
    output_template = f"{download_path}/{unix_timestamp}_{date_string}_{video_title}"

    # Check if the video has already been downloaded by comparing video titles
    existing_file = check_existing_file(video_title, download_path)
    if existing_file:
        print(f"File already exists: {existing_file}. Skipping download.")
        return f"Skipped: {video_title}"

    # Use yt-dlp to download the video only if it doesn't exist
    yt_dlp_command = [
        'yt-dlp', '--download-archive', archive_path,
        '-o', f"{output_template}.%(ext)s", f"https://www.youtube.com/watch?v={video_id}"
    ]
    try:
        subprocess.run(yt_dlp_command, check=True)
        print(f"Downloaded: {output_template}")
        return f"Downloaded: {video_title}"
    except subprocess.CalledProcessError as e:
        print(f"Error downloading video {video_title}: {e}")
        return f"Failed: {video_title}"


def download_videos(videos, download_path, max_workers=20):
    # Define the archive file path in the same folder as the downloaded videos
    archive_path = os.path.join(download_path, "archive.txt")

    total_videos = len(videos)
    processed_videos = 0
    skipped_videos = 0  # Track skipped videos

    # Use ThreadPoolExecutor to download videos in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all download tasks to the executor
        future_to_video = {
            executor.submit(download_video, video, download_path, archive_path): video for video in videos
        }

        for future in as_completed(future_to_video):
            video = future_to_video[future]
            try:
                result = future.result()
                if result.startswith("Downloaded"):
                    processed_videos += 1
                elif result.startswith("Skipped"):
                    skipped_videos += 1
            except Exception as e:
                print(f"Exception occurred for video {video['name']}: {e}")
                skipped_videos += 1

    # Final summary
    print(f"Download complete. {processed_videos} videos downloaded, {skipped_videos} videos skipped.")


def main():
    # Call the function from the imported module to ensure videos.json is up-to-date
    ytdlp_prerun.check_and_update_videos_json()

    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Download videos.")

    parser.add_argument('--start_date', default=None, type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument('--end_date', default=None, type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument('--folder', default=None, type=str, help="Download path")
    parser.add_argument('--max_workers', default=10, type=int, help="Maximum number of parallel downloads")

    # Parse the arguments from the command line
    args = parser.parse_args()

    # If arguments are not provided, prompt the user for input
    if args.start_date is None:
        args.start_date = input("Enter the start date (YYYY-MM-DD): ")

    if args.end_date is None:
        args.end_date = input("Enter the end date (YYYY-MM-DD): ")

    if args.folder is None:
        args.folder = input("Enter the download path: ")

    # Ensure the download path exists, create if not
    if not os.path.exists(args.folder):
        os.makedirs(args.folder)

    # Load videos from the JSON file
    videos = load_videos_json()  # Updated function call

    # Filter videos by the date range provided by the user
    filtered_videos = filter_videos_by_date(videos, args.start_date, args.end_date)

    # Print how many videos will be downloaded
    video_count = len(filtered_videos)
    if video_count == 0:
        print(f"No videos found between {args.start_date} and {args.end_date}.")
        return
    else:
        print(f"{video_count} videos will be downloaded from {args.start_date} to {args.end_date}.")

    # Download the videos in parallel
    download_videos(filtered_videos, args.folder, args.max_workers)

    # Print a success message
    print(f"Downloaded videos from {args.start_date} to {args.end_date} to {args.folder}.")


if __name__ == "__main__":
    main()

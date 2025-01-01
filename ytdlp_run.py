import os
import subprocess
import argparse
import signal
import threading
import ytdlp_prerun  # Import the module that checks and updates videos.json
from concurrent.futures import ThreadPoolExecutor, as_completed
from common_functions import sanitize_filename
from common_functions import get_unix_timestamp_and_date_string  # Updated to use the combined function
from common_functions import load_videos_json  # Using the updated load_videos_json
from common_functions import check_existing_file
from common_functions import filter_videos_by_date

# Global event for shutdown
shutdown_event = threading.Event()
processes = []  # List to track running yt-dlp subprocesses


def signal_handler(signum, frame):
    print("\nSignal received, initiating graceful shutdown...")
    shutdown_event.set()

    # Terminate all running yt-dlp processes
    for process in processes:
        if process.poll() is None:  # If process is still running
            process.terminate()  # Send termination signal to subprocess


# Register the signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def download_video(video, download_path, archive_path):
    if shutdown_event.is_set():
        return f"Skipped (shutdown): {video['name']}"

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
        # Only print one message about the skipped video due to existing file
        return f"File already exists: {existing_file}. Skipped: {video_title}"

    # Print that the download is starting
    print(f"Starting download: {video_title}")

    # Use yt-dlp to download the video only if it doesn't exist
    yt_dlp_command = [
        'yt-dlp', '--download-archive', archive_path,
        '-o', f"{output_template}.%(ext)s", f"https://www.youtube.com/watch?v={video_id}"
    ]
    try:
        # Start the yt-dlp process and add it to the list of processes
        # Suppress standard output, but capture errors
        process = subprocess.Popen(yt_dlp_command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        processes.append(process)

        process.wait()  # Wait for the process to finish

        if process.returncode == 0:
            return f"Downloaded: {video_title}"
        else:
            stderr_output = process.stderr.read()
            if "Sign in to confirm you’re not a bot" in stderr_output:
                print(f"Error: {video_title} requires sign-in or verification. Stopping downloads.")
                shutdown_event.set()  # Trigger shutdown to stop further downloads
                return f"Failed: {video_title} (Sign-in required)"
            else:
                print(f"Error downloading video {video_title}: {stderr_output}")
                return f"Failed: {video_title}"
    except Exception as e:
        if shutdown_event.is_set():
            print(f"Shutdown in progress. Skipping download of {video_title}.")
            return f"Skipped (shutdown): {video_title}"
        else:
            print(f"Unexpected error downloading video {video_title}: {e}")
            return f"Failed: {video_title}"


def download_videos(videos, download_path, max_workers=20):
    # Define the archive file path in the same folder as the downloaded videos
    archive_path = os.path.join(download_path, "archive.txt")

    total_videos = len(videos)
    downloaded_videos = 0  # This now includes both downloaded and skipped videos
    skipped_videos = 0  # Track skipped videos

    # Use ThreadPoolExecutor to download videos in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all download tasks to the executor
        future_to_video = {
            executor.submit(download_video, video, download_path, archive_path): video for video in videos
        }

        try:
            for future in as_completed(future_to_video):
                if shutdown_event.is_set():
                    print("Shutdown event detected. Cancelling pending tasks...")
                    break
                video = future_to_video[future]
                try:
                    result = future.result()
                    # Whether downloaded or skipped, count it as a processed video
                    downloaded_videos += 1

                    if "Skipped" in result:
                        skipped_videos += 1

                    # Display the running total of downloaded videos (downloaded + skipped)
                    print(f"{result} ({downloaded_videos}/{total_videos} downloaded)")
                except Exception as e:
                    print(f"Exception occurred for video {video['name']}: {e}")
                    downloaded_videos += 1

        except KeyboardInterrupt:
            print("\nKeyboardInterrupt received, shutting down...")
            shutdown_event.set()
            # Terminate running processes
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            # Cancel pending futures
            for future in future_to_video:
                future.cancel()
        finally:
            executor.shutdown(wait=False)

    # Final summary
    print(f"\nDownload complete. {downloaded_videos} videos downloaded, {skipped_videos} videos skipped.")


def main():
    # Call the function from the imported module to ensure videos.json is up-to-date
    ytdlp_prerun.check_and_update_videos_json()

    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Download videos.")

    parser.add_argument('--start_date', default=None, type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument('--end_date', default=None, type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument('--folder', default=None, type=str, help="Download path")
    parser.add_argument('--max_workers', default=1, type=int, help="Maximum number of parallel downloads")

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

    try:
        # Download the videos in parallel
        download_videos(filtered_videos, args.folder, args.max_workers)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received in main, exiting...")
    finally:
        if shutdown_event.is_set():
            print("Graceful shutdown complete.")

    # Print a success message
    print(f"Downloaded videos from {args.start_date} to {args.end_date} to {args.folder}.")


if __name__ == "__main__":
    main()
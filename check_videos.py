import os
from common_functions import sanitize_filename, load_videos_json
import datetime


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


def compare_videos_with_directory(videos, directory, year):
    """
    Compares the videos from videos.json for a specific year with the videos in the directory.
    Reports statistics and any videos that are missing or need preprocessing.
    """
    expected_titles = set()
    for video in videos:
        published_at = video['publishedAt']
        video_year = datetime.datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").year
        if str(video_year) == year:
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

    print(f"Year: {year}")
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

    if not missing_titles and not downloaded_only:
        print("\nAll expected videos for the year are downloaded and preprocessed.")


def main():
    # Load videos from videos.json
    videos = load_videos_json()

    # Specify the directory containing the video files for a specific year
    directory = input("Enter the directory containing video files for the specific year: ").strip()

    # Ensure the directory exists
    if not os.path.isdir(directory):
        print(f"Error: The directory '{directory}' does not exist.")
        return

    # Get the year from the user
    year = input("Enter the year to check (e.g., 2014): ").strip()

    # Validate the year
    if not year.isdigit() or len(year) != 4:
        print("Error: Please enter a valid 4-digit year.")
        return

    # Compare the videos with the directory
    compare_videos_with_directory(videos, directory, year)


if __name__ == "__main__":
    main()

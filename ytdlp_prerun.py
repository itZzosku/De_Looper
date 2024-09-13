import json
import os
from datetime import datetime, timedelta
from googleapiclient.discovery import build


def fetch_videos_from_youtube(filename='videos.json'):
    # Load API key from config.json
    with open('config.json', 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    # Get the API key from the config
    api_key = config['Youtube_API_Key']
    # The username or handle of the channel (e.g., @niilo22)
    username = "niilo22"
    # Build the service object
    youtube = build("youtube", "v3", developerKey=api_key)

    def get_channel_id(username):
        # Make a request to get the channel ID by username or handle
        request = youtube.channels().list(
            part="id",
            forUsername=username
        )
        response = request.execute()

        if not response['items']:
            # If the username does not return anything, try using 'forUsername' with the handle format
            request = youtube.channels().list(
                part="id",
                forUsername=username
            )
            response = request.execute()

        return response['items'][0]['id']

    def get_videos_from_channel(channel_id):
        # Make a request to get the uploads playlist ID
        request = youtube.channels().list(
            part="contentDetails",
            id=channel_id
        )
        response = request.execute()

        # Get the uploads playlist ID
        uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Get all videos from the uploads playlist
        videos = []
        next_page_token = None
        video_count = 0  # Initialize the video counter

        while True:
            playlist_request = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            playlist_response = playlist_request.execute()

            for item in playlist_response['items']:
                video_id = item['snippet']['resourceId']['videoId']
                video_title = item['snippet']['title']
                published_at = item['snippet']['publishedAt']
                videos.append({
                    'id': video_id,
                    'name': video_title,
                    'publishedAt': published_at
                })

                # Increment the video counter and print the progress
                video_count += 1
                print(f"Processed video {video_count}: {video_title}")

            next_page_token = playlist_response.get('nextPageToken')

            if next_page_token is None:
                break

        print(f"Total videos processed: {video_count}")
        return videos

    def assign_video_numbers(videos):
        # Sort the video list so the oldest is first
        videos = sorted(videos, key=lambda x: x['publishedAt'])

        # Assign video numbers (oldest is 1, newest has the highest number)
        for index, video in enumerate(videos):
            video['videoNumber'] = index + 1

        return videos

    def save_videos_to_json(videos, filename):
        # Add a timestamp indicating when the data was last updated
        data = {
            'lastUpdated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'videos': videos
        }
        # Save video data to a JSON file with proper encoding for special characters
        with open(filename, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)

    # Fetch the channel ID using the username
    channel_id = get_channel_id(username)

    # Fetch videos
    videos = get_videos_from_channel(channel_id)

    # Assign video numbers (oldest gets number 1)
    videos = assign_video_numbers(videos)

    # Save videos to a JSON file
    save_videos_to_json(videos, filename)

    # Print a success message
    print(f"Video data has been saved to {filename}.")


def check_and_update_videos_json(filename='videos.json'):
    data_needs_update = False

    if os.path.exists(filename):
        try:
            # Load the JSON data
            with open(filename, 'r', encoding='utf-8') as json_file:
                data = json.load(json_file)
            # Check if data is a dictionary
            if isinstance(data, dict):
                # Get the last updated timestamp
                last_updated_str = data.get('lastUpdated', None)
                if last_updated_str:
                    last_updated = datetime.strptime(last_updated_str, '%Y-%m-%dT%H:%M:%SZ')
                    if (datetime.utcnow() - last_updated) > timedelta(hours=6):
                        data_needs_update = True
                        print(f"{filename} is older than 6 hours. Fetching new data...")
                    else:
                        print(f"{filename} is up to date. No need to fetch new data.")
                else:
                    data_needs_update = True
                    print(f"'lastUpdated' timestamp not found in {filename}. Fetching new data...")
            else:
                data_needs_update = True
                print(f"{filename} has an unexpected format. Fetching new data...")
        except (json.JSONDecodeError, ValueError):
            data_needs_update = True
            print(f"Error reading {filename}. It may be corrupt. Fetching new data...")
    else:
        data_needs_update = True
        print(f"{filename} does not exist. Fetching new data...")

    if data_needs_update:
        fetch_videos_from_youtube(filename)


if __name__ == "__main__":
    check_and_update_videos_json()

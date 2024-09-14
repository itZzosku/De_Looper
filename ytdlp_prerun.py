import json
import os
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def fetch_videos_from_youtube(existing_video_ids, existing_videos, filename='videos.json'):
    # Load API key from config.json
    with open('config.json', 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
    # Get the API key from the config
    api_key = config['Youtube_API_Key']
    # The username or handle of the channel (e.g., 'niilo22')
    username = "niilo22"
    # Build the service object
    youtube = build("youtube", "v3", developerKey=api_key)

    def get_channel_id(username):
        # Try to get the channel ID using 'forUsername'
        try:
            request = youtube.channels().list(
                part="id",
                forUsername=username
            )
            response = request.execute()

            if response['items']:
                return response['items'][0]['id']
        except HttpError:
            pass  # Continue to next method if 'forUsername' fails

        # If 'forUsername' fails, use 'channels.list' with 'id' parameter
        request = youtube.channels().list(
            part="id",
            id=username.replace('@', '')  # Remove '@' if present
        )
        response = request.execute()

        if response['items']:
            return response['items'][0]['id']

        # If still not found, use 'search.list' to find the channel by username or handle
        search_request = youtube.search().list(
            part="snippet",
            q=username,
            type="channel",
            maxResults=1
        )
        search_response = search_request.execute()
        if search_response['items']:
            return search_response['items'][0]['snippet']['channelId']

        raise Exception(f"Channel with username or handle '{username}' not found.")

    def get_videos_from_channel(channel_id, existing_video_ids):
        # Get the uploads playlist ID
        request = youtube.channels().list(
            part="contentDetails",
            id=channel_id
        )
        response = request.execute()

        uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        videos = []
        next_page_token = None
        video_count = 0
        stop_fetching = False

        while not stop_fetching:
            playlist_request = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            playlist_response = playlist_request.execute()

            page_videos = []
            for item in playlist_response['items']:
                video_id = item['snippet']['resourceId']['videoId']
                if existing_video_ids and video_id in existing_video_ids:
                    print(f"Video {video_id} already exists in database. Stopping fetch.")
                    stop_fetching = True
                    break
                video_title = item['snippet']['title']
                published_at = item['snippet']['publishedAt']
                page_videos.append({
                    'id': video_id,
                    'name': video_title,
                    'publishedAt': published_at
                })
                video_count += 1
                print(f"Fetched new video {video_count}: {video_title}")

            # Add the page's videos to the main list
            videos.extend(page_videos)

            if stop_fetching:
                break

            next_page_token = playlist_response.get('nextPageToken')
            if not next_page_token:
                break

        print(f"Total new videos fetched: {video_count}")
        return videos

    def assign_video_numbers(videos):
        # Collect existing videoNumbers
        existing_video_numbers = [video['videoNumber'] for video in existing_videos if 'videoNumber' in video]

        # Combine existing and new videos
        combined_videos = existing_videos + videos

        # Remove duplicates based on video ID
        combined_videos_dict = {video['id']: video for video in combined_videos}
        combined_videos = list(combined_videos_dict.values())

        # Sort the combined list of videos by publication date (oldest first)
        combined_videos.sort(key=lambda x: x['publishedAt'])

        # Assign video numbers
        for index, video in enumerate(combined_videos):
            video['videoNumber'] = index + 1

        return combined_videos

    def save_videos_to_json(videos, filename):
        # Add a timestamp indicating when the data was last updated
        data = {
            'lastUpdated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'videos': videos
        }
        # Save video data to a JSON file with proper encoding for special characters
        with open(filename, 'w', encoding='utf-8') as json_file:
            json.dump(data, json_file, ensure_ascii=False, indent=4)

    # Fetch the channel ID using the username
    channel_id = get_channel_id(username)

    # Fetch new videos from the channel
    new_videos = get_videos_from_channel(channel_id, existing_video_ids)

    # Assign video numbers and combine with existing videos
    updated_videos = assign_video_numbers(new_videos)

    # Save the updated list to JSON
    save_videos_to_json(updated_videos, filename)

    # Return the updated videos
    return updated_videos


def check_and_update_videos_json(filename='videos.json'):
    data_needs_update = False
    existing_videos = []
    existing_video_ids = set()
    data = None

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
                    # Parse last_updated_str and make it timezone-aware
                    last_updated = datetime.strptime(last_updated_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                    # Now both datetime objects are timezone-aware in UTC
                    if (datetime.now(timezone.utc) - last_updated) > timedelta(hours=6):
                        data_needs_update = True
                        print(f"{filename} is older than 6 hours. Fetching new data...")
                    else:
                        print(f"{filename} is up to date. No need to fetch new data.")
                    # Load existing videos
                    existing_videos = data.get('videos', [])
                    existing_video_ids = set(video['id'] for video in existing_videos)
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
        # Fetch new videos and update
        updated_videos = fetch_videos_from_youtube(existing_video_ids, existing_videos, filename)
        # Print a success message
        print(f"Video data has been updated and saved to {filename}.")


if __name__ == "__main__":
    check_and_update_videos_json()

import json
from googleapiclient.discovery import build

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
        # If the username does not return anything, use the 'forUsername' key for @handle format
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
    # Reverse the video list so the oldest is first
    videos = sorted(videos, key=lambda x: x['publishedAt'])

    # Assign video numbers (oldest is 1, newest has the highest number)
    for index, video in enumerate(videos):
        video['videoNumber'] = index + 1

    return videos


def save_videos_to_json(videos, filename='videos.json'):
    # Save video data to a JSON file with proper encoding for special characters
    with open(filename, 'w', encoding='utf-8') as json_file:
        json.dump(videos, json_file, ensure_ascii=False, indent=4)


# Fetch the channel ID using the username
channel_id = get_channel_id(username)

# Fetch videos
videos = get_videos_from_channel(channel_id)

# Assign video numbers in reverse (oldest gets number 1)
videos = assign_video_numbers(videos)

# Save videos to a JSON file
save_videos_to_json(videos)

# Print a success message
print(f"Video data has been saved to videos.json.")

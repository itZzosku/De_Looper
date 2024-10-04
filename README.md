# De_Looper
De_Looper is an automated video playback system designed for seamless streaming of preprocessed video clips. It manages playlists, tracks the last played video using an ID system, and supports large video directories with metadata like video titles and release dates.

## Features

- **Automated Video Playback:** Seamlessly stream video clips in order, starting from any specified clip.
- **Track Last Played Video:** Uses video ID for accurate tracking of the last streamed video.
- **JSON Playlist Management:** Store video metadata such as name, ID, and release date.
- **File Name Parsing:** Automatically extracts video names from filenames.
- **yt-dlp Support:** Download videos with special character support in filenames.
- **Bitrate Normalization:** Preprocess videos to a consistent 2300k bitrate.
- **Multiple Video Folders:** Supports multiple input folders for video processing.



### Prerequisites

- Python 3.x
- yt-dlp
- FFmpeg

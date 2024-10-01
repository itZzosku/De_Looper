import whisper
import os
import torch

print("GPU Available: ", torch.cuda.is_available())

# Path to your video folder
video_folder = r'E:\Niilo22\2013'

# Path to the 'transcribes' subfolder
transcribes_folder = os.path.join(video_folder, 'transcribes')

# Create the 'transcribes' folder if it doesn't exist
if not os.path.exists(transcribes_folder):
    os.makedirs(transcribes_folder)

# Load the Whisper 'medium' model
model = whisper.load_model("medium")  # Use the medium model

# Get list of video files
video_files = [f for f in os.listdir(video_folder) if f.endswith(".mp4")]

# Total number of video files
total_files = len(video_files)

# Loop through all the video files
for idx, video_file in enumerate(video_files):
    video_path = os.path.join(video_folder, video_file)

    # Check if the transcription file already exists
    transcript_file = os.path.join(transcribes_folder, video_file.replace('.mp4', '_transcript.txt'))
    if os.path.exists(transcript_file):
        print(f"Skipping already transcribed file: {video_file}")
        continue

    # Print progress for the current video
    print(f"Transcribing video {idx + 1}/{total_files}: {video_file}")

    try:
        # Transcribe the video in Finnish
        result = model.transcribe(video_path, language='fi')  # 'fi' is the language code for Finnish

        # Save the transcription to a text file in the 'transcribes' folder with UTF-8 encoding
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(result['text'])

        print(f"Transcription completed for: {video_file}")
    except Exception as e:
        print(f"Failed to transcribe {video_file}: {e}")
        # Optionally, log the error to a file or take other action

print("All transcriptions are complete.")

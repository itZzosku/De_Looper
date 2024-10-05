import whisper
import os
import torch

print("GPU Available: ", torch.cuda.is_available())

# Base folder containing all subfolders with videos
base_folder = r'E:\Niilo22'

# Load the Whisper 'medium' model
model = whisper.load_model("medium")  # Use the medium model

# Walk through all subdirectories in the base folder
for root, dirs, files in os.walk(base_folder):
    print(f"Processing folder: {root}")

    # Path to the 'transcribes' subfolder in the current directory
    transcribes_folder = os.path.join(root, 'transcribes')

    # Create the 'transcribes' folder if it doesn't exist
    if not os.path.exists(transcribes_folder):
        os.makedirs(transcribes_folder)

    # Get list of video files in the current directory
    video_files = [f for f in files if f.endswith(".mp4")]

    # Total number of video files in the current directory
    total_files = len(video_files)

    # Loop through all the video files in the current directory
    for idx, video_file in enumerate(video_files):
        video_path = os.path.join(root, video_file)

        # Check if the transcription file already exists
        transcript_file = os.path.join(transcribes_folder, video_file.replace('.mp4', '_transcript.txt'))
        if os.path.exists(transcript_file):
            print(f"Skipping already transcribed file: {video_file}")
            continue

        # Print progress for the current video
        print(f"Transcribing video {idx + 1}/{total_files} in folder {root}: {video_file}")

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

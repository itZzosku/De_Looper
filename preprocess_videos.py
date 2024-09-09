import os
import subprocess

# Define the directory containing the video files
video_directory = 'E:\\Niilo22\\2023\\'  # Update this with your directory


# Function to preprocess video files, rename them with _processed, and delete the original
def preprocess_videos():
    for filename in os.listdir(video_directory):
        if filename.endswith('.mp4') and not filename.endswith('_processed.mp4'):
            input_file = os.path.join(video_directory, filename)
            output_file = os.path.join(video_directory, filename.replace('.mp4', '_processed.mp4'))

            print(f"Preprocessing {input_file}...")

            # FFmpeg command to preprocess the video with GPU acceleration (h264_nvenc) and benchmark
            subprocess.run([
                'ffmpeg',
                '-loglevel', 'error',  # Corrected: separate loglevel and error
                '-benchmark',  # Enable benchmarking to display detailed processing times
                '-i', input_file,
                '-s', '1280x720',  # Scale to 720p
                '-c:v', 'h264_nvenc', '-preset', 'fast', '-b:v', '2300k',  # Use h264_nvenc for GPU encoding
                '-r', '30',  # Set frame rate to 30fps
                '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',  # AAC audio
                '-movflags', '+faststart',  # Fast start for streaming
                output_file
            ])

            # Remove the original file after preprocessing
            os.remove(input_file)
            print(f"Original file deleted, and preprocessed file saved as: {output_file}")


# Main function to run the preprocessing
if __name__ == '__main__':
    preprocess_videos()

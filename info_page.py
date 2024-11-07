import json
import time
import re
from datetime import datetime
from collections import defaultdict

# Load the JSON data with the correct encoding
with open('videos.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extract the list of videos from the 'videos' key
videos = data['videos']

# Load the duration cache
with open('duration_cache.json', 'r', encoding='utf-8') as f:
    duration_cache = json.load(f)


# Helper function to format duration from seconds to HH:MM:SS
def format_duration(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


# Combine video data with durations
video_data = []
for video in videos:
    video_id = video['id']
    upload_date_str = video['publishedAt']  # Use 'publishedAt' instead of 'upload_date'
    name = video.get('name', 'Untitled')  # Use 'name' instead of 'title'

    # Parse the ISO 8601 date string
    try:
        # Remove 'Z' if present and parse the date string
        upload_date = datetime.strptime(upload_date_str.rstrip('Z'), '%Y-%m-%dT%H:%M:%S')
    except ValueError as e:
        print(f"Error parsing date '{upload_date_str}' for video ID {video_id}: {e}")
        continue  # Skip this video if date parsing fails

    # Convert 'upload_date' to Unix timestamp (integer)
    timestamp = int(time.mktime(upload_date.timetuple()))

    # Format the date as 'YYYYMMDD'
    date_str = upload_date.strftime('%Y%m%d')

    # Clean the name to remove or replace invalid filename characters
    # Remove characters that are not allowed in filenames
    cleaned_name = re.sub(r'[\\/*?:"<>|]', "", name)

    # Construct the expected filename
    filename = f"{timestamp}_{date_str}_{cleaned_name}_processed.mp4"

    # Get the duration from 'duration_cache.json' using the constructed filename
    duration = duration_cache.get(filename, 0)  # Get duration or default to 0

    # Append to the video data list
    video_data.append({
        'id': video_id,
        'title': name,
        'duration': duration,
        'upload_date': upload_date
    })

# Aggregate durations and counts by year, month, and day
duration_by_year = defaultdict(float)
duration_by_month = defaultdict(float)
duration_by_day = defaultdict(float)
videos_per_year = defaultdict(int)
videos_per_month = defaultdict(int)
videos_per_day = defaultdict(int)

for video in video_data:
    year = video['upload_date'].year
    month = video['upload_date'].strftime('%Y-%m')
    day = video['upload_date'].strftime('%Y-%m-%d')
    duration = video['duration']

    duration_by_year[year] += duration
    duration_by_month[month] += duration
    duration_by_day[day] += duration

    videos_per_year[year] += 1
    videos_per_month[month] += 1
    videos_per_day[day] += 1

# Calculate total statistics
total_duration = sum(video['duration'] for video in video_data)
total_videos = len(video_data)
average_duration = total_duration / total_videos if total_videos else 0

# Start building the HTML content
html_content = '''
<!DOCTYPE html>
<html>
<head>
    <title>Video Content Statistics</title>
    <style>
        body { font-family: Arial, sans-serif; }
        h2 { color: #2e6c80; }
        table { width: 80%; border-collapse: collapse; margin-bottom: 20px; }
        th, td { border: 1px solid #ccc; padding: 8px; text-align: right; }
        th { background-color: #f2f2f2; }
        caption { caption-side: top; text-align: left; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Video Content Statistics</h1>
'''

# Add total statistics
html_content += f'''
    <h2>Total Statistics</h2>
    <p><strong>Total Videos:</strong> {total_videos}</p>
    <p><strong>Total Duration:</strong> {format_duration(total_duration)}</p>
    <p><strong>Average Video Length:</strong> {format_duration(average_duration)}</p>
'''


# Function to generate a table
def generate_table(title, headers, rows):
    table_html = f'<table>\n<caption>{title}</caption>\n<tr>'
    for header in headers:
        table_html += f'<th>{header}</th>'
    table_html += '</tr>\n'
    for row in rows:
        table_html += '<tr>'
        for cell in row:
            table_html += f'<td>{cell}</td>'
        table_html += '</tr>\n'
    table_html += '</table>\n'
    return table_html


# Prepare data for duration by year
years = sorted(duration_by_year.keys())
year_rows = []
for year in years:
    total_year_duration = duration_by_year[year]
    avg_duration = total_year_duration / videos_per_year[year] if videos_per_year[year] else 0
    year_rows.append([
        year,
        format_duration(total_year_duration),
        videos_per_year[year],
        format_duration(avg_duration)  # Average duration per video
    ])

# Add duration by year table
html_content += generate_table(
    "Duration by Year",
    ["Year", "Total Duration", "Number of Videos", "Average Duration per Video"],
    year_rows
)

# Prepare data for duration by month
months = sorted(duration_by_month.keys())
month_rows = []
for month in months:
    total_month_duration = duration_by_month[month]
    avg_duration = total_month_duration / videos_per_month[month] if videos_per_month[month] else 0
    month_rows.append([
        month,
        format_duration(total_month_duration),
        videos_per_month[month],
        format_duration(avg_duration)
    ])

# Add duration by month table
html_content += generate_table(
    "Duration by Month",
    ["Month", "Total Duration", "Number of Videos", "Average Duration per Video"],
    month_rows
)

# Prepare data for top 10 longest videos
top_videos = sorted(video_data, key=lambda x: x['duration'], reverse=True)[:10]
top_video_rows = []
for video in top_videos:
    top_video_rows.append([
        video['title'],
        video['upload_date'].strftime('%Y-%m-%d'),
        format_duration(video['duration'])
    ])

# Add top 10 longest videos table
html_content += generate_table(
    "Top 10 Longest Videos",
    ["Title", "Upload Date", "Duration"],
    top_video_rows
)

# Close the HTML content
html_content += '''
</body>
</html>
'''

# Write to an HTML file
with open('video_statistics.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("HTML page 'video_statistics.html' has been generated successfully.")

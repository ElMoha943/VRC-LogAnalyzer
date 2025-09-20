# VRChat Log Analyzer Web App

A local web application for analyzing VRChat log files to determine which users were online during specific time periods.

## Features

- Per Instance sections
- Sortable table columns
- Tracks amount of join/leaves and total playtime of each user
- Clickable usernames that redirect you to the users profile.

## Requirements

- Python 3.7+
- Flask (automatically installed)

Install dependencies:
```bash
pip install -r requirements.txt
```

## Run the app

1. **Start the web application:**
   ```bash
   python web_app.py
   ```

2. **Open your browser and go to:**
   ```
   http://127.0.0.1:5000
   ```

3. **Upload your log file and specify the time range you want to analyze**

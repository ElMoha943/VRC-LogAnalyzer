#!/usr/bin/env python3
"""
VRChat Log Analyzer Web Application

A Flask web app that allows users to upload VRChat log files and analyze
which users were online during a specific time period.
"""

from flask import Flask, render_template, request, flash, redirect, url_for
import re
import os
from datetime import datetime
from collections import defaultdict
import tempfile

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Configure upload settings
UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'log', 'txt'}

def allowed_file(filename):
    """Check if file has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_timestamp(timestamp_str):
    """Parse timestamp from log format or datetime-local format."""
    try:
        # Try log format first: 2025.08.31 04:47:35
        return datetime.strptime(timestamp_str, "%Y.%m.%d %H:%M:%S")
    except ValueError:
        try:
            # Try datetime-local format: 2025-08-31T04:47:35 or 2025-08-31T04:47
            if 'T' in timestamp_str:
                if len(timestamp_str.split('T')[1].split(':')) == 2:
                    # Add seconds if not provided
                    timestamp_str += ':00'
                return datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S")
            else:
                # Try standard format: 2025-08-31 04:47:35
                return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

def parse_log_events(log_content):
    """Parse join and leave events from log content."""
    username_to_events = defaultdict(lambda: {'joins': [], 'leaves': []})
    
    lines = log_content.split('\n')
    
    # Parse join events - use OnPlayerJoinComplete for full usernames
    join_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*OnPlayerJoinComplete (.+?)(?:\s*$)'
    
    # Parse leave events
    leave_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*OnPlayerLeft (.+?) \((.+?)\)'
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check for join events
        join_match = re.search(join_pattern, line)
        if join_match:
            timestamp_str, username = join_match.groups()
            username = username.strip()
            timestamp = parse_timestamp(timestamp_str)
            if timestamp:
                username_to_events[username]['joins'].append(timestamp)
            continue
        
        # Check for leave events
        leave_match = re.search(leave_pattern, line)
        if leave_match:
            timestamp_str, username, _ = leave_match.groups()
            timestamp = parse_timestamp(timestamp_str)
            if timestamp:
                username_to_events[username]['leaves'].append(timestamp)
    
    return username_to_events

def get_users_online_during_period(username_to_events, start_time, end_time):
    """Get list of users who were online during the specified time period."""
    online_users = []
    
    for username, events in username_to_events.items():
        joins = sorted(events['joins'])
        leaves = sorted(events['leaves'])
        
        # Check if user was online during any part of the specified period
        user_was_online = False
        
        # Create timeline of user's online/offline status
        is_online = False
        last_status_change = None
        
        # Merge and sort all events
        all_events = []
        for join_time in joins:
            all_events.append((join_time, 'join'))
        for leave_time in leaves:
            all_events.append((leave_time, 'leave'))
        
        all_events.sort()
        
        # Check if user was online at start of period
        # Look at status just before start_time
        for event_time, event_type in all_events:
            if event_time <= start_time:
                if event_type == 'join':
                    is_online = True
                elif event_type == 'leave':
                    is_online = False
            else:
                break
        
        # If user was already online at start of period
        if is_online:
            user_was_online = True
        
        # Check events during the period
        for event_time, event_type in all_events:
            if start_time <= event_time <= end_time:
                if event_type == 'join':
                    user_was_online = True
                    is_online = True
                elif event_type == 'leave':
                    is_online = False
        
        if user_was_online:
            # Calculate how long they were online during the period
            online_duration = calculate_online_duration_in_period(
                joins, leaves, start_time, end_time
            )
            online_users.append({
                'username': username,
                'total_joins': len(joins),
                'total_leaves': len(leaves),
                'online_duration_minutes': round(online_duration / 60, 1),
                'first_join': min(joins) if joins else None,
                'last_leave': max(leaves) if leaves else None
            })
    
    # Sort by username
    online_users.sort(key=lambda x: x['username'].lower())
    return online_users

def calculate_online_duration_in_period(joins, leaves, start_time, end_time):
    """Calculate how long a user was online during the specified period."""
    if not joins:
        return 0
    
    duration = 0
    joins = sorted(joins)
    leaves = sorted(leaves)
    
    # Merge events to create timeline
    all_events = []
    for join_time in joins:
        all_events.append((join_time, 'join'))
    for leave_time in leaves:
        all_events.append((leave_time, 'leave'))
    
    all_events.sort()
    
    is_online = False
    online_start = None
    
    # Determine initial state before start_time
    for event_time, event_type in all_events:
        if event_time <= start_time:
            if event_type == 'join':
                is_online = True
                online_start = max(event_time, start_time)
            elif event_type == 'leave':
                is_online = False
                online_start = None
        else:
            break
    
    # If user was online at start of period
    if is_online and online_start is None:
        online_start = start_time
    
    # Process events during the period
    for event_time, event_type in all_events:
        if event_time > end_time:
            break
            
        if event_time >= start_time:
            if event_type == 'join' and not is_online:
                is_online = True
                online_start = event_time
            elif event_type == 'leave' and is_online and online_start:
                duration += (event_time - online_start).total_seconds()
                is_online = False
                online_start = None
    
    # If still online at end of period
    if is_online and online_start:
        duration += (end_time - online_start).total_seconds()
    
    return duration

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Check if file was uploaded
        if 'log_file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['log_file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if not allowed_file(file.filename):
            flash('Invalid file type. Please upload a .log or .txt file', 'error')
            return redirect(request.url)
        
        # Get time inputs
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        
        if not start_time_str or not end_time_str:
            flash('Please provide both start and end times', 'error')
            return redirect(request.url)
        
        # Parse times
        start_time = parse_timestamp(start_time_str)
        end_time = parse_timestamp(end_time_str)
        
        if not start_time or not end_time:
            flash('Invalid time format. Please use the datetime picker.', 'error')
            return redirect(request.url)
        
        if start_time >= end_time:
            flash('Start time must be before end time', 'error')
            return redirect(request.url)
        
        try:
            # Read and parse log file
            log_content = file.read().decode('utf-8')
            username_to_events = parse_log_events(log_content)
            
            if not username_to_events:
                flash('No join/leave events found in the log file', 'warning')
                return redirect(request.url)
            
            # Get users online during specified period
            online_users = get_users_online_during_period(username_to_events, start_time, end_time)
            
            # Calculate statistics
            total_join_events = sum(len(events['joins']) for events in username_to_events.values())
            total_leave_events = sum(len(events['leaves']) for events in username_to_events.values())
            
            return render_template('results.html',
                                 users=online_users,
                                 start_time=start_time,
                                 end_time=end_time,
                                 total_users=len(online_users),
                                 total_join_events=total_join_events,
                                 total_leave_events=total_leave_events,
                                 filename=file.filename)
        
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'error')
            return redirect(request.url)
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

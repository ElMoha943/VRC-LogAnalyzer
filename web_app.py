from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import os
import re
from datetime import datetime
from collections import defaultdict
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a random secret key

# Configuration
UPLOAD_FOLDER = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'log', 'txt'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def parse_timestamp(timestamp_str):
    """Parse timestamp from log format."""
    try:
        return datetime.strptime(timestamp_str, "%Y.%m.%d %H:%M:%S")
    except ValueError:
        return None

def parse_log_file_with_sessions(file_path):
    """Parse the log file and extract sessions with join/leave events."""
    sessions = []
    current_session = None
    
    # Patterns for parsing events
    join_complete_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*OnPlayerJoinComplete (.+?)(?:\s*$)'
    join_with_id_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*OnPlayerJoined (.+?) \((usr_[a-f0-9\-]+)\)'
    leave_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*OnPlayerLeft (.+?) \((usr_[a-f0-9\-]+)\)'
    
    # Patterns for session detection
    world_join_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*\[Behaviour\] Joining (wrld_[a-f0-9\-:~\(\)_]+)'
    room_join_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*\[Behaviour\] Joining or Creating Room: (.+?)(?:\s*$)'
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                # Check for world/room joining (session start)
                world_match = re.search(world_join_pattern, line)
                room_match = re.search(room_join_pattern, line)
                
                if world_match:
                    timestamp_str, world_id = world_match.groups()
                    timestamp = parse_timestamp(timestamp_str)
                    if timestamp:
                        # Start new session
                        current_session = {
                            'session_start': timestamp,
                            'world_id': world_id,
                            'room_name': None,  # Will be filled by next room join
                            'join_events': [],
                            'leave_events': []
                        }
                        sessions.append(current_session)
                
                elif room_match and current_session:
                    timestamp_str, room_name = room_match.groups()
                    timestamp = parse_timestamp(timestamp_str)
                    if timestamp:
                        current_session['room_name'] = room_name.strip()
                
                # Check for join events (try both patterns)
                join_complete_match = re.search(join_complete_pattern, line)
                join_with_id_match = re.search(join_with_id_pattern, line)
                
                if (join_complete_match or join_with_id_match) and current_session:
                    if join_with_id_match:
                        # OnPlayerJoined with user ID
                        timestamp_str, username, user_id = join_with_id_match.groups()
                    else:
                        # OnPlayerJoinComplete without user ID
                        timestamp_str, username = join_complete_match.groups()
                        user_id = None
                    
                    username = username.strip()
                    timestamp = parse_timestamp(timestamp_str)
                    if timestamp:
                        current_session['join_events'].append({
                            'timestamp': timestamp,
                            'username': username,
                            'user_id': user_id,
                            'line_num': line_num
                        })
                
                # Check for leave events
                leave_match = re.search(leave_pattern, line)
                if leave_match and current_session:
                    timestamp_str, username, user_id = leave_match.groups()
                    username = username.strip()
                    timestamp = parse_timestamp(timestamp_str)
                    if timestamp:
                        current_session['leave_events'].append({
                            'timestamp': timestamp,
                            'username': username,
                            'user_id': user_id,
                            'line_num': line_num
                        })
    
    except Exception as e:
        print(f"Error parsing file: {e}")
        return []
    
    return sessions

def process_session_users(session, start_time=None, end_time=None):
    """Process users for a specific session and return user statistics."""
    username_to_events = defaultdict(lambda: {'joins': [], 'leaves': [], 'user_id': None})
    
    # Collect events by username for this session
    for event in session['join_events']:
        username_to_events[event['username']]['joins'].append(event['timestamp'])
        if event.get('user_id'):
            username_to_events[event['username']]['user_id'] = event['user_id']
    
    for event in session['leave_events']:
        username_to_events[event['username']]['leaves'].append(event['timestamp'])
        if event.get('user_id'):
            username_to_events[event['username']]['user_id'] = event['user_id']
    
    session_users = []
    
    for username, events in username_to_events.items():
        joins = sorted(events['joins'])
        leaves = sorted(events['leaves'])
        
        # Calculate online periods within this session
        user_online_periods = []
        all_events = []
        
        for join_time in joins:
            all_events.append(('join', join_time))
        for leave_time in leaves:
            all_events.append(('leave', leave_time))
        
        all_events.sort(key=lambda x: x[1])
        
        is_online = False
        current_join_time = None
        
        for event_type, timestamp in all_events:
            if event_type == 'join' and not is_online:
                is_online = True
                current_join_time = timestamp
            elif event_type == 'leave' and is_online:
                if current_join_time:
                    user_online_periods.append((current_join_time, timestamp))
                is_online = False
                current_join_time = None
        
        # If user is still online at the end of session
        if is_online and current_join_time:
            # Use the session end or last event time
            last_event_time = max(timestamp for _, timestamp in all_events) if all_events else current_join_time
            user_online_periods.append((current_join_time, last_event_time))
        
        # Calculate total online duration in this session
        total_online_seconds = sum((end - start).total_seconds() for start, end in user_online_periods)
        
        # Apply time filter if provided
        if start_time and end_time:
            # Filter periods to only include time within the specified range
            filtered_duration = 0
            for period_start, period_end in user_online_periods:
                overlap_start = max(period_start, start_time)
                overlap_end = min(period_end, end_time)
                if overlap_start < overlap_end:
                    filtered_duration += (overlap_end - overlap_start).total_seconds()
            total_online_seconds = filtered_duration
            
            # Only include users who were online during the time range
            was_online_during_range = any(
                period_start <= end_time and period_end >= start_time
                for period_start, period_end in user_online_periods
            )
            if not was_online_during_range:
                continue
        
        session_users.append({
            'username': username,
            'user_id': events['user_id'],
            'total_joins': len(joins),
            'total_leaves': len(leaves),
            'online_duration_minutes': total_online_seconds / 60,
            'first_join': min(joins) if joins else None,
            'last_leave': max(leaves) if leaves else None
        })
    
    return sorted(session_users, key=lambda x: x['username'].lower())

def parse_log_file(file_path):
    """Parse the log file and extract join/leave events (legacy function for backward compatibility)."""
    sessions = parse_log_file_with_sessions(file_path)
    
    # Flatten all events from all sessions for backward compatibility
    join_events = []
    leave_events = []
    
    for session in sessions:
        join_events.extend(session['join_events'])
        leave_events.extend(session['leave_events'])
    
    return join_events, leave_events

def get_users_at_time_range(join_events, leave_events, start_time, end_time):
    """Get users who were online during the specified time range. If start_time and end_time are None, returns all users."""
    username_to_events = defaultdict(lambda: {'joins': [], 'leaves': [], 'user_id': None})
    
    # Collect all events by username
    for event in join_events:
        username_to_events[event['username']]['joins'].append(event['timestamp'])
        if event.get('user_id'):
            username_to_events[event['username']]['user_id'] = event['user_id']

    for event in leave_events:
        username_to_events[event['username']]['leaves'].append(event['timestamp'])
        if event.get('user_id'):
            username_to_events[event['username']]['user_id'] = event['user_id']

    users_in_range = []

    for username, events in username_to_events.items():
        joins = sorted(events['joins'])
        leaves = sorted(events['leaves'])
        
        # If no time range specified, include all users
        if start_time is None or end_time is None:
            # Calculate total time online across all periods
            user_online_periods = []
            
            # Create timeline of user's online periods
            all_events = []
            for join_time in joins:
                all_events.append(('join', join_time))
            for leave_time in leaves:
                all_events.append(('leave', leave_time))
            
            all_events.sort(key=lambda x: x[1])
            
            is_online = False
            current_join_time = None
            
            for event_type, timestamp in all_events:
                if event_type == 'join' and not is_online:
                    is_online = True
                    current_join_time = timestamp
                elif event_type == 'leave' and is_online:
                    if current_join_time:
                        user_online_periods.append((current_join_time, timestamp))
                    is_online = False
                    current_join_time = None
            
            # If user is still online at the end
            if is_online and current_join_time:
                # Use current time or last event time as end
                last_timestamp = max(timestamp for _, timestamp in all_events) if all_events else current_join_time
                user_online_periods.append((current_join_time, last_timestamp))
            
            # Calculate total online time
            total_online_seconds = sum((end - start).total_seconds() for start, end in user_online_periods)
            
            users_in_range.append({
                'username': username,
                'user_id': events['user_id'],
                'total_joins': len(joins),
                'total_leaves': len(leaves),
                'online_duration_minutes': total_online_seconds / 60,
                'first_join': min(joins) if joins else None,
                'last_leave': max(leaves) if leaves else None
            })
            continue        # Process all events chronologically
        all_events = []
        for join_time in joins:
            all_events.append(('join', join_time))
        for leave_time in leaves:
            all_events.append(('leave', leave_time))
        
        all_events.sort(key=lambda x: x[1])
        
        for event_type, timestamp in all_events:
            if event_type == 'join' and not is_online:
                is_online = True
                current_join_time = timestamp
            elif event_type == 'leave' and is_online:
                if current_join_time:
                    user_online_periods.append((current_join_time, timestamp))
                is_online = False
                current_join_time = None
        
        # If user is still online at the end
        if is_online and current_join_time:
            # Use the last event timestamp as end time
            last_timestamp = max(timestamp for _, timestamp in all_events) if all_events else current_join_time
            user_online_periods.append((current_join_time, last_timestamp))
        
        # Check if any online period overlaps with the requested time range
        was_online_during_range = False
        for period_start, period_end in user_online_periods:
            # Check if periods overlap
            if period_start <= end_time and period_end >= start_time:
                was_online_during_range = True
                break
        
        if was_online_during_range:
            # Calculate how long they were online during the specified range
            total_overlap = 0
            for period_start, period_end in user_online_periods:
                overlap_start = max(period_start, start_time)
                overlap_end = min(period_end, end_time)
                if overlap_start < overlap_end:
                    total_overlap += (overlap_end - overlap_start).total_seconds()
            
            users_in_range.append({
                'username': username,
                'user_id': events['user_id'],
                'total_joins': len(joins),
                'total_leaves': len(leaves),
                'online_duration_minutes': total_overlap / 60,
                'first_join': min(joins) if joins else None,
                'last_leave': max(leaves) if leaves else None
            })
    
    return sorted(users_in_range, key=lambda x: x['username'].lower())

@app.route('/')
def index():
    """Main page with upload form."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and time range analysis."""
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(url_for('index'))
    
    file = request.files['file']
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('index'))
    
    # Handle optional date range
    start_time = None
    end_time = None
    
    # Check if both dates are provided or both are empty
    if start_time_str and end_time_str:
        try:
            # Parse the time inputs from datetime-local format (YYYY-MM-DDTHH:MM)
            # Convert T to space and add seconds if missing
            start_time_formatted = start_time_str.replace('T', ' ')
            end_time_formatted = end_time_str.replace('T', ' ')
            
            # Add seconds if not present
            if len(start_time_formatted) == 16:  # YYYY-MM-DD HH:MM
                start_time_formatted += ':00'
            if len(end_time_formatted) == 16:  # YYYY-MM-DD HH:MM
                end_time_formatted += ':00'
            
            start_time = datetime.strptime(start_time_formatted, "%Y-%m-%d %H:%M:%S")
            end_time = datetime.strptime(end_time_formatted, "%Y-%m-%d %H:%M:%S")
            
            if start_time >= end_time:
                flash('Start time must be before end time')
                return redirect(url_for('index'))
                
        except ValueError as e:
            flash(f'Invalid time format: {str(e)}')
            return redirect(url_for('index'))
    elif start_time_str or end_time_str:
        # Only one date provided - require both or neither
        flash('Please provide both start and end times, or leave both empty to analyze all logs')
        return redirect(url_for('index'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # Parse the log file with sessions
            sessions = parse_log_file_with_sessions(file_path)
            
            # Process users for each session
            for session in sessions:
                session['users'] = process_session_users(session, start_time, end_time)
            
            # Also get flattened events for backward compatibility with existing functions
            join_events, leave_events = parse_log_file(file_path)
            
            # Get users in the specified time range
            users_in_range = get_users_at_time_range(join_events, leave_events, start_time, end_time)
            
            # Clean up the temporary file
            os.remove(file_path)
            
            return render_template('results.html', 
                                 users=users_in_range,
                                 sessions=sessions,
                                 start_time=start_time,
                                 end_time=end_time,
                                 total_users=len(users_in_range),
                                 total_join_events=len(join_events),
                                 total_leave_events=len(leave_events))
            
        except Exception as e:
            # Clean up the temporary file if there was an error
            if os.path.exists(file_path):
                os.remove(file_path)
            flash(f'Error processing file: {str(e)}')
            return redirect(url_for('index'))
    else:
        flash('Invalid file type. Please upload a .log or .txt file')
        return redirect(url_for('index'))

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """API endpoint for programmatic access."""
    try:
        data = request.get_json()
        
        if not data or 'log_content' not in data or 'start_time' not in data or 'end_time' not in data:
            return jsonify({'error': 'Missing required fields: log_content, start_time, end_time'}), 400
        
        # Parse times
        start_time = datetime.strptime(data['start_time'], "%Y-%m-%d %H:%M:%S")
        end_time = datetime.strptime(data['end_time'], "%Y-%m-%d %H:%M:%S")
        
        # Create temporary file with log content
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as temp_file:
            temp_file.write(data['log_content'])
            temp_file_path = temp_file.name
        
        try:
            # Parse the log content
            join_events, leave_events = parse_log_file(temp_file_path)
            
            # Get users in the specified time range
            users_in_range = get_users_at_time_range(join_events, leave_events, start_time, end_time)
            
            return jsonify({
                'users': users_in_range,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'total_users': len(users_in_range),
                'total_join_events': len(join_events),
                'total_leave_events': len(leave_events)
            })
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    
    except ValueError as e:
        return jsonify({'error': f'Invalid time format: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Error processing request: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)

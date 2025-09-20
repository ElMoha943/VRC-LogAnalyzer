#!/usr/bin/env python3
"""
VRChat Log Analyzer - Determines which users were online at the end of the session.

This script analyzes join and leave events from VRChat logs to determine:
1. Which users were online at the end of the session
2. Session duration for each user
3. Timeline of user activity

Usage: python online_users_analyzer.py <joins_file> <leaves_file>
"""

import re
import sys
from datetime import datetime
from collections import defaultdict, OrderedDict

class UserSession:
    """Represents a user's session with join/leave times."""
    
    def __init__(self, username, user_id):
        self.username = username
        self.user_id = user_id
        self.join_times = []
        self.leave_times = []
        self.is_online = False
        self.total_duration = 0
    
    def add_join(self, timestamp):
        """Add a join event."""
        self.join_times.append(timestamp)
        self.is_online = True
    
    def add_leave(self, timestamp):
        """Add a leave event."""
        self.leave_times.append(timestamp)
        self.is_online = False
    
    def calculate_final_status(self):
        """Determine if user is online based on join/leave events."""
        # If more joins than leaves, user is online
        # If equal joins and leaves, user is offline
        # If more leaves than joins, there's an issue with the data
        
        if len(self.join_times) > len(self.leave_times):
            self.is_online = True
        elif len(self.join_times) == len(self.leave_times):
            self.is_online = False
        else:
            # More leaves than joins - might indicate user was already online at start
            self.is_online = False
    
    def calculate_total_duration(self):
        """Calculate total time spent online."""
        duration = 0
        
        # Pair up join/leave times chronologically
        joins = sorted(self.join_times)
        leaves = sorted(self.leave_times)
        
        join_idx = 0
        leave_idx = 0
        is_currently_online = False
        last_join_time = None
        
        # Create a timeline of all events
        all_events = []
        for join_time in joins:
            all_events.append(('join', join_time))
        for leave_time in leaves:
            all_events.append(('leave', leave_time))
        
        # Sort events by timestamp
        all_events.sort(key=lambda x: x[1])
        
        # Process events chronologically
        for event_type, timestamp in all_events:
            if event_type == 'join' and not is_currently_online:
                is_currently_online = True
                last_join_time = timestamp
            elif event_type == 'leave' and is_currently_online:
                if last_join_time:
                    session_duration = (timestamp - last_join_time).total_seconds()
                    duration += session_duration
                is_currently_online = False
                last_join_time = None
        
        # If user is still online at the end
        if is_currently_online and last_join_time and all_events:
            # Use the last event timestamp as end time reference
            last_event_time = max(timestamp for _, timestamp in all_events)
            duration += (last_event_time - last_join_time).total_seconds()
        
        self.total_duration = duration
        return duration

def parse_timestamp(timestamp_str):
    """Parse timestamp from log format."""
    try:
        # Format: 2025.08.31 04:47:35
        return datetime.strptime(timestamp_str, "%Y.%m.%d %H:%M:%S")
    except ValueError as e:
        print(f"Error parsing timestamp '{timestamp_str}': {e}")
        return None

def parse_join_events(joins_file):
    """Parse join events from the joins file."""
    join_events = []
    
    # Use only OnPlayerJoinComplete events as they have full usernames
    join_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*OnPlayerJoinComplete (.+?)(?:\s*$)'
    
    try:
        with open(joins_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                match = re.search(join_pattern, line)
                if match:
                    timestamp_str, username = match.groups()
                    username = username.strip()  # Remove any trailing whitespace
                    
                    timestamp = parse_timestamp(timestamp_str)
                    if timestamp:
                        join_events.append({
                            'timestamp': timestamp,
                            'username': username,
                            'user_id': f"unknown_{username}",  # We don't have user IDs for JoinComplete events
                            'line_num': line_num
                        })
                        
    except FileNotFoundError:
        print(f"Error: Joins file '{joins_file}' not found.")
        return []
    except Exception as e:
        print(f"Error reading joins file: {e}")
        return []
    
    return join_events

def parse_leave_events(leaves_file):
    """Parse leave events from the leaves file."""
    leave_events = []
    
    # Pattern for leave events
    leave_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*OnPlayerLeft (.+?) \((.+?)\)'
    
    try:
        with open(leaves_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                match = re.search(leave_pattern, line)
                if match:
                    timestamp_str, username, user_id = match.groups()
                    timestamp = parse_timestamp(timestamp_str)
                    if timestamp:
                        leave_events.append({
                            'timestamp': timestamp,
                            'username': username,
                            'user_id': user_id,
                            'line_num': line_num
                        })
                        
    except FileNotFoundError:
        print(f"Error: Leaves file '{leaves_file}' not found.")
        return []
    except Exception as e:
        print(f"Error reading leaves file: {e}")
        return []
    
    return leave_events

def analyze_user_sessions(join_events, leave_events):
    """Analyze join/leave events to determine user sessions."""
    users = {}
    
    # First, try to match users by username (since IDs might be inconsistent)
    username_to_events = defaultdict(lambda: {'joins': [], 'leaves': []})
    
    # Collect all events by username
    for event in join_events:
        username_to_events[event['username']]['joins'].append(event)
    
    for event in leave_events:
        username_to_events[event['username']]['leaves'].append(event)
    
    # Create user sessions
    for username, events in username_to_events.items():
        # Use the most common user_id for this username, or first available
        user_ids = []
        for join_event in events['joins']:
            if join_event['user_id'] != f"unknown_{username}":
                user_ids.append(join_event['user_id'])
        for leave_event in events['leaves']:
            if leave_event['user_id'] != f"unknown_{username}":
                user_ids.append(leave_event['user_id'])
        
        # Get the most common user_id or use unknown
        if user_ids:
            user_id = max(set(user_ids), key=user_ids.count)
        else:
            user_id = f"unknown_{username}"
        
        # Create user session
        user_session = UserSession(username, user_id)
        
        # Add all join events
        for join_event in events['joins']:
            user_session.add_join(join_event['timestamp'])
        
        # Add all leave events  
        for leave_event in events['leaves']:
            user_session.add_leave(leave_event['timestamp'])
        
        # Calculate final status
        user_session.calculate_final_status()
        user_session.calculate_total_duration()
        
        users[username] = user_session
    
    return users

def print_results(users):
    """Print analysis results."""
    online_users = []
    offline_users = []
    
    for user_session in users.values():
        if user_session.is_online:
            online_users.append(user_session)
        else:
            offline_users.append(user_session)
    
    # Sort by username
    online_users.sort(key=lambda x: x.username.lower())
    offline_users.sort(key=lambda x: x.username.lower())
    
    print("=" * 80)
    print("VRChat Session Analysis Results")
    print("=" * 80)
    
    print(f"\n🟢 USERS ONLINE AT END OF SESSION ({len(online_users)} users):")
    print("-" * 50)
    if online_users:
        for user in online_users:
            join_count = len(user.join_times)
            leave_count = len(user.leave_times)
            duration_min = user.total_duration / 60
            print(f"  • {user.username}")
            print(f"    Joins: {join_count}, Leaves: {leave_count}, Duration: {duration_min:.1f} min")
            if join_count > 0:
                first_join = min(user.join_times).strftime("%H:%M:%S")
                last_activity = max(user.join_times + user.leave_times).strftime("%H:%M:%S")
                print(f"    First join: {first_join}, Last activity: {last_activity}")
    else:
        print("  No users online at end of session")
    
    print(f"\n🔴 USERS OFFLINE AT END OF SESSION ({len(offline_users)} users):")
    print("-" * 50)
    if offline_users:
        for user in offline_users:
            join_count = len(user.join_times)
            leave_count = len(user.leave_times)
            duration_min = user.total_duration / 60
            print(f"  • {user.username}")
            print(f"    Joins: {join_count}, Leaves: {leave_count}, Duration: {duration_min:.1f} min")
            if user.join_times or user.leave_times:
                all_times = user.join_times + user.leave_times
                first_activity = min(all_times).strftime("%H:%M:%S")
                last_activity = max(all_times).strftime("%H:%M:%S")
                print(f"    First activity: {first_activity}, Last activity: {last_activity}")
    else:
        print("  No users were offline at end of session")
    
    print(f"\n📊 SUMMARY:")
    print("-" * 20)
    print(f"Total unique users: {len(users)}")
    print(f"Online at end: {len(online_users)}")
    print(f"Offline at end: {len(offline_users)}")
    
    # Timeline summary
    if users:
        all_timestamps = []
        for user in users.values():
            all_timestamps.extend(user.join_times)
            all_timestamps.extend(user.leave_times)
        
        if all_timestamps:
            session_start = min(all_timestamps)
            session_end = max(all_timestamps)
            session_duration = (session_end - session_start).total_seconds() / 60
            
            print(f"Session start: {session_start}")
            print(f"Session end: {session_end}")
            print(f"Total session duration: {session_duration:.1f} minutes")
    
    # Create a simple list of online users
    print(f"\n📋 SIMPLE LIST OF ONLINE USERS:")
    print("-" * 30)
    for user in online_users:
        print(f"  {user.username}")
    
    return online_users, offline_users

def main():
    """Main function."""
    if len(sys.argv) != 3:
        print("Usage: python online_users_analyzer.py <joins_file> <leaves_file>")
        print("\nExample:")
        print("  python online_users_analyzer.py 'Data Day1/Joins1.txt' 'Data Day1/Lefts1.txt'")
        sys.exit(1)
    
    joins_file = sys.argv[1]
    leaves_file = sys.argv[2]
    
    print(f"Analyzing join events from: {joins_file}")
    print(f"Analyzing leave events from: {leaves_file}")
    print("\nProcessing...")
    
    # Parse events
    join_events = parse_join_events(joins_file)
    leave_events = parse_leave_events(leaves_file)
    
    print(f"Found {len(join_events)} join events")
    print(f"Found {len(leave_events)} leave events")
    
    if not join_events and not leave_events:
        print("No events found. Please check your input files.")
        sys.exit(1)
    
    # Analyze sessions
    users = analyze_user_sessions(join_events, leave_events)
    
    # Print results
    print_results(users)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Simple Online Users Extractor - Creates a clean list of users online at the end.

This is a simplified version that just outputs the list of online users to a text file.

Usage: python simple_online_users.py <joins_file> <leaves_file> [output_file]
"""

import re
import sys
from datetime import datetime
from collections import defaultdict

def parse_timestamp(timestamp_str):
    """Parse timestamp from log format."""
    try:
        return datetime.strptime(timestamp_str, "%Y.%m.%d %H:%M:%S")
    except ValueError:
        return None

def parse_events(joins_file, leaves_file):
    """Parse both join and leave events."""
    username_to_events = defaultdict(lambda: {'joins': [], 'leaves': []})
    
    # Parse join events - use only OnPlayerJoinComplete as they have full usernames
    join_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*OnPlayerJoinComplete (.+?)(?:\s*$)'
    
    try:
        with open(joins_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                match = re.search(join_pattern, line)
                if match:
                    timestamp_str, username = match.groups()
                    username = username.strip()  # Remove any trailing whitespace
                    
                    timestamp = parse_timestamp(timestamp_str)
                    if timestamp:
                        username_to_events[username]['joins'].append(timestamp)
    except FileNotFoundError:
        print(f"Error: Joins file '{joins_file}' not found.")
        return {}
    
    # Parse leave events
    leave_pattern = r'(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}).*OnPlayerLeft (.+?) \((.+?)\)'
    
    try:
        with open(leaves_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                match = re.search(leave_pattern, line)
                if match:
                    timestamp_str, username, _ = match.groups()
                    timestamp = parse_timestamp(timestamp_str)
                    if timestamp:
                        username_to_events[username]['leaves'].append(timestamp)
    except FileNotFoundError:
        print(f"Error: Leaves file '{leaves_file}' not found.")
        return {}
    
    return username_to_events

def get_online_users(username_to_events):
    """Determine which users are online at the end."""
    online_users = []
    
    for username, events in username_to_events.items():
        join_count = len(events['joins'])
        leave_count = len(events['leaves'])
        
        # If more joins than leaves, user is online
        if join_count > leave_count:
            online_users.append(username)
    
    return sorted(online_users, key=str.lower)

def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python simple_online_users.py <joins_file> <leaves_file> [output_file]")
        print("\nExample:")
        print("  python simple_online_users.py 'Data Day1/Joins1.txt' 'Data Day1/Lefts1.txt'")
        print("  python simple_online_users.py 'Data Day1/Joins1.txt' 'Data Day1/Lefts1.txt' online_users.txt")
        sys.exit(1)
    
    joins_file = sys.argv[1]
    leaves_file = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"Analyzing: {joins_file} and {leaves_file}")
    
    # Parse events
    username_to_events = parse_events(joins_file, leaves_file)
    
    if not username_to_events:
        print("No events found. Please check your input files.")
        sys.exit(1)
    
    # Get online users
    online_users = get_online_users(username_to_events)
    
    # Output results
    print(f"\nFound {len(online_users)} users online at the end of session:")
    
    output_lines = []
    for user in online_users:
        print(f"  {user}")
        output_lines.append(user)
    
    # Save to file if specified
    if output_file:
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                for user in online_users:
                    f.write(user + '\n')
            print(f"\nList saved to: {output_file}")
        except Exception as e:
            print(f"Error saving to file: {e}")
    
    print(f"\nTotal: {len(online_users)} users online")

if __name__ == "__main__":
    main()

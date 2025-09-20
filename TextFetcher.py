#!/usr/bin/env python3
"""
Script to extract all lines containing a given pattern from a text file
and save them to a new file.
"""

import re
import sys

def extract_lines_with_pattern(input_file, output_file, pattern, case_sensitive=True):
    """
    Extract lines containing a pattern from input file and write to output file.
    
    Args:
        input_file (str): Path to the input file
        output_file (str): Path to the output file
        pattern (str): Pattern to search for
        case_sensitive (bool): Whether the search should be case sensitive
    """
    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        
        with open(input_file, 'r', encoding='utf-8') as infile:
            matching_lines = []
            
            for line_num, line in enumerate(infile, 1):
                if re.search(pattern, line, flags):
                    matching_lines.append(line.rstrip('\n\r'))
        
        # Write matching lines to output file
        with open(output_file, 'w', encoding='utf-8') as outfile:
            for line in matching_lines:
                outfile.write(line + '\n')
        
        print(f"Found {len(matching_lines)} lines matching pattern '{pattern}'")
        print(f"Results saved to: {output_file}")
        
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False
    
    return True

def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) < 4:
        print("Usage: python test.py <input_file> <output_file> <pattern> [case_sensitive]")
        print("Example: python test.py input.txt output.txt 'OnPlayerJoinComplete'")
        print("Example: python test.py input.txt output.txt 'error' false")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    pattern = sys.argv[3]
    case_sensitive = True
    
    if len(sys.argv) > 4:
        case_sensitive = sys.argv[4].lower() not in ['false', 'f', '0', 'no']
    
    success = extract_lines_with_pattern(input_file, output_file, pattern, case_sensitive)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()

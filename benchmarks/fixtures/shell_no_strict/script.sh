#!/bin/bash
# Shell script WITHOUT strict mode - findings should NOT be suppressed

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/myscript.log"

# Function: Process file (missing error handling)
process_file() {
    input_file="$1"
    output_file="${input_file%.txt}.processed"

    # Missing: no check if file exists
    while read line; do
        echo "Processed: $line" >> "$output_file"
    done < "$input_file"
}

# Main entry point
main() {
    input_dir="${1:-./input}"

    # Missing: no check if directory exists
    for file in "$input_dir"/*.txt; do
        process_file "$file"
    done
}

main "$@"

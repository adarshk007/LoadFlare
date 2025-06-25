#!/usr/bin/env python3

import subprocess
import shlex
import argparse
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import re

def execute_curl(command_args, request_num, original_curl_string):
    """
    Executes a single curl command, prints its output, and returns the result.
    Now more robustly captures and displays the HTTP status code and precise timestamps.

    Args:
        command_args (list): The curl command split into a list of arguments (after extracting -n/--requests).
        request_num (int): The global number of the current request for logging.
        original_curl_string (str): The original string of the curl command as provided by the user.

    Returns:
        tuple: A tuple containing (return_code, http_status_code, duration, original_curl_string).
               http_status_code will be None if not found or an error occurred.
    """
    request_sent_time = datetime.now()
    
    # Construct the modified command args
    # We want to ensure:
    # 1. 'curl'
    # 2. '-s' (silent mode - essential for clean output for -w)
    # 3. '-L' (follow redirects - to get final status code)
    # 4. '-w "%{http_code}\n"' (write HTTP code to stdout at the end)
    # 5. All other original arguments that were part of the actual curl command.
    
    modified_command_args = [command_args[0]] # Start with 'curl'
    
    # Add silent and follow redirects if not already present
    if '-s' not in command_args and '--silent' not in command_args:
        modified_command_args.append('-s')
    if '-L' not in command_args and '--location' not in command_args:
        modified_command_args.append('-L')
        
    # Add the write-out format for http_code
    modified_command_args.extend(['-w', '%{http_code}\n'])
    
    # Add the rest of the actual curl command arguments, excluding any conflicting -w flags
    # This list (`command_args`) has already had our custom -n/-c flags removed by main().
    skip_next = False
    for arg in command_args[1:]:
        if skip_next:
            skip_next = False
            continue
        if arg == '-w' or arg == '--write-out':
            skip_next = True # Skip the next argument as it's the format string
            continue
        modified_command_args.append(arg)

    print(f"[Request {request_num}] Firing... (Command: '{original_curl_string}') (Sent at: {request_sent_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]})")
    
    start_time_monotonic = time.monotonic()
    process = None
    try:
        process = subprocess.run(
            modified_command_args,
            capture_output=True,
            text=True,
            check=False
        )
        duration = time.monotonic() - start_time_monotonic
        output_received_time = datetime.now()
        
        http_status_code = None
        actual_stdout = process.stdout.strip()
        
        # Regex to find the HTTP status code (3 digits) at the very end of stdout
        match = re.search(r'(\d{3})\n?$', actual_stdout)
        if match:
            http_status_code = int(match.group(1))
            # Remove the status code from the actual_stdout content
            actual_stdout = actual_stdout[:match.start()].strip()


        # --- Print Detailed Result for This Request ---
        print(f"\n--- Result for Request {request_num} (Command: '{original_curl_string}') ---")
        print(f"Request Sent: {request_sent_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        print(f"Output Received: {output_received_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (Took {duration:.2f}s)")
        
        # Determine Response Status
        if process.returncode == 0:
            if http_status_code is not None:
                if 200 <= http_status_code < 400:
                    print("Response Status: Correct (HTTP OK/Redirect)")
                elif 400 <= http_status_code < 500:
                    print("Response Status: Client Error")
                elif 500 <= http_status_code < 600:
                    print("Response Status: Server Error")
                else:
                    print("Response Status: Other HTTP Status")
                print(f"HTTP Status Code: {http_status_code}")
            else:
                print("Response Status: Success (No HTTP Status Code found - possibly non-HTTP or parsing issue)")
        else:
            print(f"Response Status: Error (Curl Exit Code: {process.returncode})")
            if http_status_code is not None:
                print(f"HTTP Status Code: {http_status_code} (Error likely before server response or non-2xx/3xx)")

        print("\nResponse Body (stdout):")
        if actual_stdout:
            indented_stdout = "\n".join([f"  {line}" for line in actual_stdout.split('\n')])
            print(indented_stdout)
        else:
            print("  [No stdout content]")

        if process.stderr:
            print("\nError Details (stderr):")
            indented_stderr = "\n".join([f"  {line}" for line in process.stderr.strip().split('\n')])
            print(indented_stderr)
        else:
            print("  [No stderr content]")
        
        print("--------------------------------------------------\n")

        return (process.returncode, http_status_code, duration, original_curl_string)

    except FileNotFoundError:
        duration = time.monotonic() - start_time_monotonic
        output_received_time = datetime.now()
        print(f"\n--- Result for Request {request_num} (Command: '{original_curl_string}') ---")
        print(f"Request Sent: {request_sent_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        print(f"Output Received: {output_received_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (Took {duration:.2f}s)")
        print("[Error] 'curl' command not found. Please ensure it's installed and in your PATH.")
        print("Response Status: Error (Command Not Found)")
        print("--------------------------------------------------\n")
        return (-1, None, duration, original_curl_string)
    except Exception as e:
        duration = time.monotonic() - start_time_monotonic
        output_received_time = datetime.now()
        print(f"\n--- Result for Request {request_num} (Command: '{original_curl_string}') ---")
        print(f"Request Sent: {request_sent_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        print(f"Output Received: {output_received_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (Took {duration:.2f}s)")
        print(f"[Error] An unexpected Python error occurred: {e}")
        print("Response Status: Error (Unexpected Python Exception)")
        print("--------------------------------------------------\n")
        return (-1, None, duration, original_curl_string)

def main():
    """
    Main function to parse arguments and run multiple concurrent requests across various curl commands.
    Allows specifying per-command request counts using -n/--requests within the command string,
    otherwise uses the global -n value.
    """
    parser = argparse.ArgumentParser(
        description="A Python script to run multiple different curl commands in parallel with detailed logging.\n"
                    "Each curl command string can specify its own number of requests using '-n' or '--requests'.\n"
                    "If not specified in a command string, the global '-n' value will be used.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "curl_commands",
        type=str,
        nargs='+', # This indicates one or more arguments
        help="One or more full curl commands to execute, each enclosed in quotes.\n"
             "Example: \"curl http://example.com -n 5\" \"curl -X POST http://api.com/data\""
    )
    parser.add_argument(
        "-n", "--requests",
        type=int,
        default=1, # Default global requests is 1
        help="The default number of times to send *each* specified curl command if no '-n' is provided within the command string."
    )
    parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=os.cpu_count() or 1,
        help="The maximum number of parallel threads (workers) to use for all requests.\n"
             "This is a global limit. Any '-c' or '--concurrency' flags specified within\n"
             "individual curl command strings will be ignored."
    )

    args = parser.parse_args()

    # Store the global requests count
    global_requests_count = args.requests

    # Prepare all tasks to be submitted
    all_tasks = []
    
    # Process each provided curl command string
    for original_cmd_str in args.curl_commands:
        try:
            temp_parsed_args = shlex.split(original_cmd_str)
            
            if not temp_parsed_args or temp_parsed_args[0] != 'curl':
                print(f"Error: Command '{original_cmd_str}' must start with 'curl'. Skipping.")
                continue

            per_cmd_requests = global_requests_count # Default to global requests count
            final_curl_args = [] # This will hold the actual curl command arguments without our custom flags

            # Iterate through the parsed arguments to extract -n/--requests and filter out -c/--concurrency
            i = 0
            while i < len(temp_parsed_args):
                arg = temp_parsed_args[i]
                if arg in ['-n', '--requests']:
                    if i + 1 < len(temp_parsed_args):
                        try:
                            per_cmd_requests = int(temp_parsed_args[i+1]) # Override with embedded value
                            i += 2 # Skip the value argument
                            continue
                        except ValueError:
                            print(f"Warning: Invalid number for '{arg}' in command '{original_cmd_str}'. Using global default ({global_requests_count}) requests.")
                    else:
                        print(f"Warning: Missing value for '{arg}' in command '{original_cmd_str}'. Using global default ({global_requests_count}) requests.")
                elif arg in ['-c', '--concurrency']:
                    print(f"Warning: Per-command concurrency '{arg}' in '{original_cmd_str}' is ignored. Global -c applies.")
                    # Skip the value argument if it exists
                    if i + 1 < len(temp_parsed_args) and not temp_parsed_args[i+1].startswith('-'):
                        i += 1 
                else:
                    final_curl_args.append(arg)
                i += 1

            if not final_curl_args:
                print(f"Error: No valid curl command arguments found after parsing '{original_cmd_str}'. Skipping.")
                continue

            # Add tasks for this command based on its per_cmd_requests count
            for _ in range(per_cmd_requests):
                all_tasks.append((final_curl_args, original_cmd_str))

        except ValueError as e:
            print(f"Error parsing curl command '{original_cmd_str}': {e}. Skipping.")
            continue
    
    if not all_tasks:
        print("No valid curl commands to execute. Exiting.")
        return

    print("--- Concurrent Request Executor (Multi-Command) ---")
    print(f"  Commands to execute ({len(args.curl_commands)} unique, {len(all_tasks)} total requests):")
    # To show correct per-command counts in the summary, store them during parsing
    command_summary_counts = {}
    for task_args, task_original_cmd in all_tasks:
        command_summary_counts[task_original_cmd] = command_summary_counts.get(task_original_cmd, 0) + 1

    for cmd_idx, cmd_str in enumerate(args.curl_commands):
        count = command_summary_counts.get(cmd_str, 0)
        print(f"    {cmd_idx + 1}. {cmd_str} ({count} times)")
    print(f"  Global Concurrency Level (Workers): {args.concurrency}")
    print("--------------------------------------------------\n")

    futures = []
    success_count = 0
    client_error_count = 0
    server_error_count = 0
    other_failure_count = 0
    
    overall_start_time = time.monotonic()

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        # Submit all the jobs to the pool
        for i, (command_args, original_cmd_str) in enumerate(all_tasks, start=1):
            future = executor.submit(execute_curl, command_args, i, original_cmd_str)
            futures.append(future)

        # Process results as they are completed
        for future in as_completed(futures):
            try:
                return_code, http_status_code, _, _ = future.result()
                if http_status_code is not None:
                    if 200 <= http_status_code < 400:
                        success_count += 1
                    elif 400 <= http_status_code < 500:
                        client_error_count += 1
                    elif 500 <= http_status_code < 600:
                        server_error_count += 1
                    else:
                        other_failure_count += 1
                elif return_code == 0:
                    other_failure_count += 1 
                else:
                    other_failure_count += 1
            except Exception as e:
                other_failure_count += 1
                print(f"An error occurred while processing a request future: {e}")

    overall_duration = time.monotonic() - overall_start_time

    print("\n--- Final Summary ---")
    print(f"Total time taken: {overall_duration:.2f} seconds")
    print(f"Total requests attempted: {len(all_tasks)}")
    print(f"  - Successful (HTTP 2xx/3xx): {success_count}")
    print(f"  - Client Errors (HTTP 4xx):  {client_error_count}")
    print(f"  - Server Errors (HTTP 5xx):  {server_error_count}")
    print(f"  - Other Failures (Curl/Network/Other HTTP): {other_failure_count}")
    print("---------------------\n")

if __name__ == "__main__":
    main()

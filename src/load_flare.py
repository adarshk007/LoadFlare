#!/usr/bin/env python3

import subprocess
import shlex
import argparse
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime # Import datetime for precise timestamps
import re # Import re for regular expressions to extract status code

def execute_curl(command_args, request_num):
    """
    Executes a single curl command, prints its output, and returns the result.
    Now also captures and displays the HTTP status code and precise timestamps.

    Args:
        command_args (list): The curl command split into a list of arguments.
        request_num (int): The number of the current request for logging.

    Returns:
        tuple: A tuple containing (return_code, http_status_code, duration).
               http_status_code will be None if not found or an error occurred.
    """
    request_sent_time = datetime.now() # Timestamp for when the request is sent
    
    # Modify the command to include -w "%{http_code}\n" to get the status code
    # We insert it after 'curl' but before any other arguments
    modified_command_args = [command_args[0], '-w', '%{http_code}\n'] + command_args[1:]

    print(f"[Request {request_num}] Firing... (Sent at: {request_sent_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]})")
    
    start_time_monotonic = time.monotonic() # For duration calculation
    process = None # Initialize process to None
    try:
        process = subprocess.run(
            modified_command_args, # Use the modified command args
            capture_output=True,
            text=True,
            check=False
        )
        duration = time.monotonic() - start_time_monotonic
        output_received_time = datetime.now() # Timestamp for when output is received
        
        http_status_code = None
        # Attempt to extract the HTTP status code from stdout
        # The -w "%{http_code}\n" makes the status code the very last line
        output_lines = process.stdout.strip().split('\n')
        if output_lines:
            # Check if the last line looks like an HTTP status code (e.g., 200, 404, 500)
            # It should be a number, typically 3 digits, but could be 000 if no response
            if re.fullmatch(r'\d+', output_lines[-1]):
                http_status_code = int(output_lines[-1])
                # Remove the status code from the actual stdout content
                actual_stdout = '\n'.join(output_lines[:-1])
            else:
                actual_stdout = process.stdout.strip() # If last line is not a status code, use full output
        else:
            actual_stdout = "" # No stdout

        # --- Print Detailed Result for This Request ---
        print(f"\n--- Result for Request {request_num} ---")
        print(f"Request Sent: {request_sent_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        print(f"Output Received: {output_received_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (Took {duration:.2f}s)")
        
        if process.returncode == 0 and http_status_code is not None and 200 <= http_status_code < 400:
            print("Response Status: Correct (HTTP OK/Redirect)")
            print(f"HTTP Status Code: {http_status_code}")
        elif http_status_code is not None:
            print(f"Response Status: Error (HTTP Status Code: {http_status_code})")
            if process.returncode != 0:
                print(f"Curl Exit Code: {process.returncode}")
        elif process.returncode == 0:
            print("Response Status: Success (No HTTP Status Code found - possibly non-HTTP or curl issue)")
        else:
            print(f"Response Status: Error (Curl Exit Code: {process.returncode}, No HTTP Status Code found)")


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
            print("\n  [No stderr content]")
        
        print("--------------------------------------------------\n")


        return (process.returncode, http_status_code, duration)

    except FileNotFoundError:
        duration = time.monotonic() - start_time_monotonic
        output_received_time = datetime.now()
        print(f"\n--- Result for Request {request_num} ---")
        print(f"Request Sent: {request_sent_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        print(f"Output Received: {output_received_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (Took {duration:.2f}s)")
        print("[Error] 'curl' command not found. Please ensure it's installed and in your PATH.")
        print("Response Status: Error (Command Not Found)")
        print("--------------------------------------------------\n")
        return (-1, None, duration)
    except Exception as e:
        duration = time.monotonic() - start_time_monotonic
        output_received_time = datetime.now()
        print(f"\n--- Result for Request {request_num} ---")
        print(f"Request Sent: {request_sent_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        print(f"Output Received: {output_received_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (Took {duration:.2f}s)")
        print(f"[Error] An unexpected error occurred: {e}")
        print("Response Status: Error (Unexpected Python Exception)")
        print("--------------------------------------------------\n")
        return (-1, None, duration)

def main():
    """
    Main function to parse arguments and run the concurrent requests.
    """
    parser = argparse.ArgumentParser(
        description="A Python script to run multiple curl commands in parallel with detailed logging.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "curl_command",
        type=str,
        help="The full curl command to execute, enclosed in quotes.\n"
             "Example: \"curl -X POST -H 'Content-Type: application/json' -d '{\"key\":\"value\"}' http://localhost:8080/api/test\""
    )
    parser.add_argument(
        "-n", "--requests",
        type=int,
        required=True,
        help="The total number of requests to send."
    )
    parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=os.cpu_count() or 1,
        help="The number of parallel threads (workers) to use.\n"
             "Defaults to the number of CPU cores on the system."
    )

    args = parser.parse_args()

    try:
        command_args = shlex.split(args.curl_command)
        if not command_args or command_args[0] != 'curl':
            print("Error: The command must start with 'curl'.")
            return
    except ValueError as e:
        print(f"Error parsing curl command: {e}")
        return

    print("--- Concurrent Request Executor ---")
    print(f"  Target Command: {args.curl_command}")
    print(f"  Total Requests: {args.requests}")
    print(f"  Concurrency Level (Workers): {args.concurrency}")
    print("---------------------------------\n")

    futures = []
    success_count = 0
    client_error_count = 0 # 4xx status codes
    server_error_count = 0 # 5xx status codes
    other_failure_count = 0 # Curl errors, network errors, etc.
    
    overall_start_time = time.monotonic()

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        for i in range(1, args.requests + 1):
            future = executor.submit(execute_curl, command_args, i)
            futures.append(future)

        for future in as_completed(futures):
            try:
                return_code, http_status_code, _ = future.result()
                if return_code == 0 and http_status_code is not None:
                    if 200 <= http_status_code < 400:
                        success_count += 1
                    elif 400 <= http_status_code < 500:
                        client_error_count += 1
                    elif 500 <= http_status_code < 600:
                        server_error_count += 1
                    else: # Other valid, but not success status codes (e.g., 1xx informational)
                        other_failure_count += 1 # Or categorize as needed
                else:
                    other_failure_count += 1 # Curl error, command not found, or no status code
            except Exception as e:
                other_failure_count += 1
                print(f"An error occurred while processing a request future: {e}")

    overall_duration = time.monotonic() - overall_start_time

    print("\n--- Final Summary ---")
    print(f"Total time taken: {overall_duration:.2f} seconds")
    print(f"Total requests sent: {args.requests}")
    print(f"  - Successful (HTTP 2xx/3xx): {success_count}")
    print(f"  - Client Errors (HTTP 4xx):  {client_error_count}")
    print(f"  - Server Errors (HTTP 5xx):  {server_error_count}")
    print(f"  - Other Failures (Curl/Network/Other HTTP): {other_failure_count}")
    print("---------------------\n")

if __name__ == "__main__":
    main()

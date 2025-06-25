# LoadFlare
Test your Code with Concurrent Requests.

```Bash
./concurrent_curl.py "curl http://httpbin.org/status/200" -n 5 -c 2
./concurrent_curl.py "curl http://httpbin.org/status/404" -n 3 -c 1
./concurrent_curl.py "curl http://httpbin.org/delay/5" -n 2 -c 2
./concurrent_curl.py "curl -X POST -H 'Content-Type: application/json' -d '{\"foo\":\"bar\"}' http://httpbin.org/post" -n 1
```

Per-command -n overrides global:

httpbin.org/status/200 runs 10 times.

httpbin.org/delay/1 runs 3 times (default 1 for the other two commands, as no -n is specified).

httpbin.org/get runs 1 time (global default).

httpbin.org/post runs 1 time (global default).

Total requests = 10+3+1+1=15.

```Bash
./concurrent_load_tester.py "curl http://httpbin.org/status/200" "curl http://httpbin.org/delay/2" -n 5 -c 4
./concurrent_load_tester.py "curl http://httpbin.org/status/200 -n 10" "curl http://httpbin.org/delay/1 -n 3" "curl http://httpbin.org/get" "curl -X POST -d '{\"foo\":\"bar\"}' http://httpbin.org/post" -c 5
./concurrent_load_tester.py "curl http://httpbin.org/status/200" "curl http://httpbin.org/status/404"
```

<h3>Method 1: Making it a Standalone Executable Command (Recommended)</h3>

This is the most common and robust way to turn a script into a command.

**Steps:**
Save your Python script: Let's say you save the updated Python script as concurrent_curl.py.

Make it executable:


```Bash
chmod +x concurrent_curl.py
```

**Move it to a directory in your $PATH:**
Your $PATH is an environment variable that lists directories where your shell looks for executable commands. Common places include:

<li> /usr/local/bin (for system-wide use) </li>

<li> ~/bin (for user-specific use; you might need to create this directory if it doesn't exist and add it to your $PATH) </li>


**Let's use ~/bin for a user-specific command:**

```Bash
mkdir -p ~/bin           # Create the directory if it doesn't exist
mv concurrent_curl.py ~/bin/cconcur # Rename it to 'cconcur' for brevity
Add ~/bin to your $PATH (if not already there):
You'll need to edit your shell's configuration file.

For Bash: ~/.bashrc or ~/.bash_profile
For Zsh: ~/.zshrc
```

**Add the following line to the end of the file:**

```Bash
export PATH="$HOME/bin:$PATH"
Note: If you already have a PATH export, just add $HOME/bin: to the beginning.
```

**Source your shell configuration file:**
After editing, apply the changes without restarting your terminal:
**For Bash:** source ~/.bashrc (or source ~/.bash_profile)
**For Zsh:** source ~/.zshrc

**Now you can run your script as a command:**

```Bash
cconcur "curl http://httpbin.org/status/200" -n 5 -c 2
cconcur "curl -X POST -H 'Content-Type: application/json' -d '{\"foo\":\"bar\"}' http://httpbin.org/post" -n 1
```

### Method 2: Shell Alias (Quick & Simple for Personal Use)

An alias is a shortcut for a command. It's good for short, frequently used commands.

**Steps:**

**Add the alias to your shell configuration file:**

**For Bash:** ~/.bashrc <br/>
**For Zsh:** ~/.zshrc

**Add a line like this:**

```Bash
alias cconcur='python3 /path/to/your/concurrent_curl.py'
Replace /path/to/your/concurrent_curl.py with the actual path to where you saved your Python script.
```

**Source your shell configuration file:**
For Bash: source ~/.bashrc
For Zsh: source ~/.zshrc

**Now you can run it using the alias:**

```Bash
cconcur "curl http://httpbin.org/status/200" -n 5 -c 2
```


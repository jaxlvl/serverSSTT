#!/bin/bash

# This script launches a Python web server with specific configurations
# Parameters:
#   -p 9000        : Sets the server port to 9000
#   -ip 127.0.0.1  : Sets the server IP to localhost
#   -wb .          : Sets the web root directory to current directory

python3 web_sstt.py -p 9000 -ip 127.0.0.1 -wb .


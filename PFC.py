#!/usr/local/bin/python3.5
import os
import subprocess
import sys

chosenProject = \
"/shome/tuliolinux/Downloads/systemc-2.3.1/examples/sysc/simple_fifo"

# Goes to project folder, compiles and save log
try:
    os.chdir(chosenProject)
except OSError:
    sys.exit("Failed to change directory")

try:
    subprocess.run("make", shell=True, check=True)
except subprocess.CalledProcessError:
    sys.exit("Failed to compile")

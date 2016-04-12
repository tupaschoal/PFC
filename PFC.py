#!/usr/local/bin/python3.5
import subprocess
import os

chosenProject = \
"/home/tuliolinux/Downloads/systemc-2.3.1/examples/sysc/simple_fifo"

# Goes to project folder, compiles and save log
os.chdir(chosenProject)
subprocess.run("ls", shell=True, check=True)
try:
    subprocess.run("make", shell=True, check=True)
except subprocess.CalledProcessError as err:
    print("Failed to compile")

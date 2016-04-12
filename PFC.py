#!/usr/local/bin/python3.5
import os
import subprocess
import sys

chosenProject = \
"/home/tuliolinux/Downloads/systemc-2.3.1/examples/sysc/simple_fifo"
cleanLogPath = "/tmp/cleanBuildLog"

# Goes to project folder, compiles and saves log
try:
    os.chdir(chosenProject)
except OSError:
    sys.exit("Failed to change directory")

try:
    subprocess.run("make", shell=True, check=True)
except subprocess.CalledProcessError:
    sys.exit("Failed to compile")

try:
    out = subprocess.run("./simple_fifo.x", shell=True, check=True, \
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        f = open(cleanLogPath,'w+b')
        f.write(out.stdout)
        f.write(out.stderr)
        f.close()
    except OSError:
        sys.exit("Failed to use file")
except subprocess.CalledProcessError:
    sys.exit("Failed to run")

# Cleanup routines, delete logs and folders
try:
    os.unlink(cleanLogPath)
except OSErros:
    sys.exit("Failed to clean files")

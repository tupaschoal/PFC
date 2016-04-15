#!/usr/local/bin/python3.5
import filecmp
import os
import re
import shutil
import subprocess
import sys

chosenProject = "simple_fifo"
path = "/home/tuliolinux/Downloads/systemc-2.3.1/examples/sysc/"
fullPath = path+chosenProject
cleanLogPath = "/tmp/cleanBuildLog"
fInjectedLogPath = "/tmp/fInjectedBuildLog"
fInjectedProj = path+"/fij"
diffPath = "/tmp/diff"

# Goes to project folder, compiles and saves log
try:
    os.chdir(fullPath)
except OSError:
    sys.exit("Failed to change directory")

try:
    subprocess.run("make", shell=True, check=True)
except subprocess.CalledProcessError:
    sys.exit("Failed to compile")

try:
    out = subprocess.run("./"+chosenProject+".x", shell=True, check=True, \
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

# Copies project folder, inject failure, compile and saves log
try:
    shutil.copytree(fullPath, fInjectedProj)
except shutil.Error:
    sys.exit("Cannot copy tree")
try:
    os.chdir(fInjectedProj)
except OSError:
    sys.exit("Failed to change directory")

regEx = re.compile('(?: ?((?:(?:un)?signed)?) int)[ \*&](\w+)[ ,\)]')

try:
    subprocess.run("make", shell=True, check=True)
except subprocess.CalledProcessError:
    sys.exit("Failed to compile")

try:
    out = subprocess.run("./"+chosenProject+".x", shell=True, check=True, \
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        f = open(fInjectedLogPath,'w+b')
        f.write(out.stdout)
        f.write(out.stderr)
        f.close()
    except OSError:
        sys.exit("Failed to use file")
except subprocess.CalledProcessError:
    sys.exit("Failed to run")

# Make diff
comparison = filecmp.cmp(cleanLogPath, fInjectedLogPath)
try:
    f = open(diffPath,'w')
    f.write(str(comparison))
    f.close()
except OSError:
    sys.exit("Failed to use file")

# Cleanup routines, delete logs and folders
try:
    os.unlink(cleanLogPath)
    os.unlink(fInjectedLogPath)
    os.unlink(diffPath)
    shutil.rmtree(fInjectedProj)
except OSError:
    sys.exit("Failed to clean files")
except shutil.Error:
    sys.exit("Failed to remove folder")

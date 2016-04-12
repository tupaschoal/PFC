#!/usr/local/bin/python3.5
import subprocess
import os

chosenProject = "/home/tuliolinux/Downloads/systemc-2.3.1/examples/sysc/"
os.chdir(chosenProject)
subprocess.call("ls")
subprocess.call("make")

#!/usr/bin/python
import subprocess
import os

chosenProject = "/home/tuliolinux/Downloads/systemc-2.3.1/examples/sysc/"
os.chdir(chosenProject)
#subprocess.call(["cd", "-1", F])
subprocess.call("ls")
subprocess.call("make")
subprocess.call("make")

#testing cache

#!/usr/local/bin/python3.5
import filecmp     #Compare execution outputs
import logging     #Ease use of debugging messages
import os          #Change folders/create/copy/delete
import random      #Choose line and values randomly
import re          #Use regEx as search pattern
import shutil      #Copy directories
import subprocess  #Run shell commands
import sys         #Exit with error code

chosenProject = "simple_fifo"
path = "/home/tuliolinux/Downloads/systemc-2.3.1/examples/sysc/"
fullPath = path+chosenProject
cleanLogPath = "/tmp/cleanBuildLog"
fInjectedLogPath = "/tmp/fInjectedBuildLog"
fInjectedProj = path+"/fij"
diffPath = "/tmp/diff"

### Script Functions ###

# Clean environment before exiting
def cleanEnv(error):
    try:
        os.unlink(cleanLogPath)
        os.unlink(fInjectedLogPath)
        os.unlink(diffPath)
        shutil.rmtree(fInjectedProj)
    except OSError:
        sys.exit("Failed to clean files")
    except shutil.Error:
        sys.exit("Failed to remove folder")
    sys.exit(error)

# Generates a random number based on type
def randomValue(dataType):
    if dataType == "char":
        return random.randint(-128,127)
    elif dataType == "float":
        return random.random()
    elif dataType == "short":
        return random.randint(-32768, 32767)
    elif dataType == "int":
        return random.getrandbits(32)
    elif dataType == "bool":
        return random.randint(0,1)
    else:
        return 0;

#### Main Script ####
logging.basicConfig(stream=sys.stderr, level=logging.NOTSET)

# Goes to project folder, compiles and saves log
try:
    os.chdir(fullPath)
except OSError:
    cleanEnv("Failed to change directory")

try:
    subprocess.run("make", shell=True, check=True)
except subprocess.CalledProcessError:
    cleanEnv("Failed to compile")

try:
    out = subprocess.run("./"+chosenProject+".x", shell=True, check=True, \
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        f = open(cleanLogPath,'w+b')
        f.write(out.stdout)
        f.write(out.stderr)
        f.close()
    except OSError:
        cleanEnv("Failed to use file")
except subprocess.CalledProcessError:
    cleanEnv("Failed to run")

# Copies project folder, inject failure, compile and saves log
try:
    shutil.copytree(fullPath, fInjectedProj)
except shutil.Error:
    cleanEnv("Cannot copy tree")
try:
    os.chdir(fInjectedProj)
except OSError:
    cleanEnv("Failed to change directory")

regEx = re.compile( #To match any variable declaration/definition
        '(int|float|short|char|bool'                    #C++ types
        '|sc_(?:bit|logic|int|uint|bigint|biguint))'    #SystemC types
        '(?:[ \*&] *\*{0,2}&{0,1} *)'                   #Skip *&' '
        '([A-Z_a-z]\w*)'                                #Variable name
        '[ ,;\)\[\]]')                                  #Ending in =);,[]

listOfMatches = []
for i, line in enumerate(open(chosenProject+'.cpp')):
    for match in re.finditer(regEx,line):
        listOfMatches.append((i+1, match.groups()))

contents = []
with open(chosenProject+'.cpp','r') as f:
    contents = f.readlines()

chooseV = False
i = 0
while not chooseV:
    i = random.randint(0, len(listOfMatches) -1)
    chooseV = listOfMatches[i][1][1] != "sc_main"

dataType = listOfMatches[i][1][0]
val = randomValue(dataType)
injectedContent = "%s = %d;" % (listOfMatches[i][1][1], val)
logging.info(" Inserting: %s" % injectedContent)
contents.insert(listOfMatches[i][0], injectedContent)

with open(chosenProject+'.cpp','w') as f:
    f.writelines(contents)

for x in listOfMatches:
    logging.info(" L: %d (T: %s V: %s)" % (x[0], x[1][0], x[1][1]))

try:
    subprocess.run("make", shell=True, check=True)
except subprocess.CalledProcessError:
    cleanEnv("Failed to compile fault injected project")

try:
    out = subprocess.run("./"+chosenProject+".x", shell=True, check=True, \
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        f = open(fInjectedLogPath,'w+b')
        f.write(out.stdout)
        f.write(out.stderr)
        f.close()
    except OSError:
        cleanEnv("Failed to use file")
except subprocess.CalledProcessError:
    cleanEnv("Failed to run")

# Make diff
comparison = filecmp.cmp(cleanLogPath, fInjectedLogPath)
try:
    f = open(diffPath,'w')
    f.write(str(comparison))
    f.close()
except OSError:
    cleanEnv("Failed to use file")

# Cleanup routines, delete logs and folders
cleanEnv("Program ran successfully")

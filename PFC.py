#!/usr/local/bin/python3.5
import filecmp     #Compare execution outputs
import logging     #Ease use of debugging messages
import os          #Change folders/create/copy/delete
import random      #Choose line and values randomly
import re          #Use regEx as search pattern
import shutil      #Copy directories
import subprocess  #Run shell commands
import sys         #Exit with error code

chosenProject = "rsa"
path = "/home/tuliolinux/Downloads/systemc-2.3.1/examples/sysc/"
fullPath = path+chosenProject
cleanLogPath = "/tmp/cleanBuildLog"
fInjectedLogPath = "/tmp/fInjectedBuildLog"
fInjectedProj = path+"/fij"
diffPath = "/tmp/diff"

randomBool = [  "#include <stdlib.h>\n", \
                "#include <time.h>\n", \
                "static bool init = false;\n", \
                "bool randomBool() {\n", \
                "   if (!init) { \n", \
                "       srand ( time(NULL) );\n", \
                "       init = true;\n", \
                "   }\n", \
                "   return rand() % 2 == 1;\n", \
                "}\n"]

### Script Functions ###

def cleanFileOrDir(path):
    if os.path.isfile(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


# Clean environment before exiting
def cleanEnv(error):
    try:
        cleanFileOrDir(cleanLogPath)
        cleanFileOrDir(fInjectedLogPath)
        cleanFileOrDir(diffPath)
        cleanFileOrDir(fInjectedProj)
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
    elif (dataType == "bigint"    or \
          dataType == "sc_int"    or \
          dataType == "sc_uint"   or \
          dataType == "sc_bigint" or \
          dataType == "sc_biguint"):
        return random.getrandbits(63)
    elif (dataType == "bool" or dataType == "sc_bit"):
        return random.randint(0,1)
    elif dataType == "sc_logic":
        return random.choice('01xz')
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
        '(const )?'
        '(bigint|int|float|short|char|bool'             #C++ types
        '|sc_(?:bit|logic|int|uint|bigint|biguint))'    #SystemC types
        '(?:\<\w*\>)?'                                  #Support bigint templates
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
    chooseV = listOfMatches[i][1][2] != "sc_main" and\
              listOfMatches[i][1][0] != "const "

line = listOfMatches[i][0]
hasConst = listOfMatches[i][1][0]
dataType = listOfMatches[i][1][1]
varName = listOfMatches[i][1][2]
val = randomValue(dataType)
injectedContent = "%s = randomBool() ? %d : %s;" % (varName, val, varName)
if re.search('\{', contents[line]):
    line += 1
logging.info(" Inserting: %s into line %s" % (injectedContent, str(line)))
contents.insert(line, injectedContent)
maliciousFile = []
maliciousFile.extend(randomBool)
maliciousFile.extend(contents)

with open(chosenProject+'.cpp','w') as f:
    f.writelines(maliciousFile)

for x in listOfMatches:
    logging.info(" L: %d (C: %s T: %s V: %s)" % (x[0], x[1][0], x[1][1],x[1][2]))

try:
    subprocess.run("make", shell=True, check=True, \
                   stderr=subprocess.PIPE)
except subprocess.CalledProcessError as e:
    sys.stderr.buffer.write(e.stderr)
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

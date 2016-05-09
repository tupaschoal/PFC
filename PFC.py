#!/usr/local/bin/python3.5
import copy        #For deep copying
import filecmp     #Compare execution outputs
import logging     #Ease use of debugging messages
import os          #Change folders/create/copy/delete
import random      #Choose line and values randomly
import re          #Use regEx as search pattern
import shutil      #Copy directories
import subprocess  #Run shell commands
import sys         #Exit with error code
from collections import namedtuple
from enum import Enum #To list regEx types

chosenProject = "at_1_phase"
path = "/home/tuliolinux/Downloads/systemc-2.3.1/examples/tlm-seg/"
chosenProject = "pipe"
path = "/home/tuliolinux/Downloads/systemc-2.3.1/examples/sysc/"
fullPath = path+chosenProject
cleanLogPath = "/tmp/cleanBuildLog"
fInjectedLogPath = "/tmp/fInjectedBuildLog"
fInjectedProj = path+"fij"
diffPath = "/tmp/diff"
d = 2

randomBool = [  "#include <stdlib.h>\n", \
                "#include <time.h>\n", \
                "static bool init = false;\n", \
                "bool randomBool() {\n", \
                "   if (!init) { \n", \
                "       srand ( time(NULL) );\n", \
                "       init = true;\n", \
                "   }\n", \
                "   return rand() %"+str(d)+"== 0;\n", \
                "}\n"]

walkReturn = namedtuple('walkReturn', 'root, file')
data = namedtuple('data', 'line, var, type')
fault = namedtuple('fault', 'line, data')
class RegExType(Enum):
    cppVariables = 1

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
    if (error):
        sys.exit(error)

# Generates a random number based on type
def randomValue(dataType):
    if dataType == "char":
        return random.randint(-128,127)
    elif dataType == "float" or \
         dataType == "double":
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

# Traverse the path received and returns the first file found
def findFirstFile(walkingPath, fileToFind):
    for root, dirs, files in os.walk(walkingPath):
        for file in files:
            if file.endswith(fileToFind):
                return walkReturn(root, file)

# Traverse the path received and returns all matching files
def findAllFiles(walkingPath, fileToFind):
    rFiles = []
    for root, dirs, files in os.walk(walkingPath):
        for file in files:
            if file.endswith(fileToFind):
                print(root, file)
                rFiles.append(walkReturn(root, file))
    return rFiles

# Change directory or finish with exception
def changeDir(path):
    try:
        os.chdir(path)
    except OSError:
        cleanEnv("Failed to change to directory %s" % path)

# Compile, run and save log
def compileRunAndSaveLog(fullPath, cleanLogPath):
    try:
        subprocess.run("make", check=True, \
                       stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        sys.stderr.buffer.write(e.stderr)
        print("Failed to compile")

    try:
        out = subprocess.run("./"+findFirstFile(fullPath, ".x").file, check=True, \
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, \
                             timeout=20)
        try:
            f = open(cleanLogPath,'w+b')
            f.write(out.stdout)
            f.write(out.stderr)
            f.close()
        except OSError:
            cleanEnv("Failed to use file")
    except subprocess.TimeoutExpired:
        print("Process ended with timeout")
    except subprocess.CalledProcessError:
        cleanEnv("Failed to run")

# Get file content
def getFileContent(filePath):
    contents = []
    with open(filePath) as f:
        contents = f.readlines()
    return contents

# Get regEx matched lines
def parseFileWithRegEx(regEx, path):
    listOfMatches = []
    for i, line in enumerate(open(path)):
        for match in re.finditer(regEx,line):
            listOfMatches.append((i+1, match.groups()))
    return listOfMatches

# Create malicious file by injecting fault at line of original
def createMaliciousFile(original, line, injectedContent):
    contents = copy.deepcopy(original)
    if re.search('\{', contents[line]):
        line += 1
    logging.info(" Inserting: %s into line %s" % (injectedContent, str(line)))
    contents.insert(line, injectedContent)
    maliciousFile = []
    maliciousFile.extend(randomBool)
    maliciousFile.extend(contents)
    return maliciousFile

# Overwrite a file with the malicious code
def writeMaliciousFile(path, maliciousFile):
    with open(path,'w') as f:
        f.writelines(maliciousFile)

# Returns a regular expression given an enum value
def getRegExFromEnum(category):
    if (category == RegExType.cppVariables):
        regEx = re.compile( #To match any variable declaration/definition
                '(const )?'
                '(bigint|int|float|short|char|bool|double'      #C++ types
                '|sc_(?:bit|logic|int|uint|bigint|biguint))'    #SystemC types
                '(?:\<\w*\>)?'                                  #Support bigint templates
                '(?:[ \*&] *\*{0,2}&{0,1} *)'                   #Skip *&' '
                '([A-Z_a-z]\w*)'                                #Variable name
                '[ ,;\)\[\]]')                                  #Ending in =);,[]
        return regEx

# Parses matches to choose data to inject
def getRandomDataToInject(listOfMatches, category):
    if (len(listOfMatches) > 0):
        i = 0
        chooseV = False
        if (category == RegExType.cppVariables):
            while not chooseV:
                i = random.randint(0, len(listOfMatches) -1)
                chooseV = listOfMatches[i][1][2] != "sc_main" and\
                          listOfMatches[i][1][0] != "const "
            rData = data(listOfMatches[i][0],\
                         listOfMatches[i][1][2],\
                         listOfMatches[i][1][1])
            injectedContent = "{0} = randomBool() ? {1} : {2};\n".format(rData.var,\
                                                                         randomValue(rData.type),\
                                                                         rData.var)
            return fault(rData.line, injectedContent)
    else:
        return 0

# Returns next valid data to inject
def getDataToInject(listOfMatches, i, category):
    chooseV = False
    if (category == RegExType.cppVariables):
        while not chooseV:
            if (len(listOfMatches) > 0 and len(listOfMatches) < i):
                chooseV = listOfMatches[i][1][2] != "sc_main" and\
                          listOfMatches[i][1][0] != "const "
                if (not chooseV):
                    i += 1
            else:
                return 0
        rData = data(listOfMatches[i][0],\
                     listOfMatches[i][1][2],\
                     listOfMatches[i][1][1])
        injectedContent = "{0} = randomBool() ? {1} : {2};\n".format(rData.var,\
                                                                     randomValue(rData.type),\
                                                                     rData.var)
        return fault(rData.line, injectedContent)

#### Main Script ####
logging.basicConfig(stream=sys.stderr, level=logging.NOTSET)
cleanEnv(0)

# Goes to project folder, compiles and saves log
compilePath = findFirstFile(fullPath, "Makefile").root
changeDir(compilePath)
compileRunAndSaveLog(fullPath, cleanLogPath)

# Copies project folder, inject failure, compile and saves log
try:
    shutil.copytree(fullPath, fInjectedProj)
except shutil.Error:
    cleanEnv("Cannot copy tree")
changeDir(fInjectedProj)

rFiles = findAllFiles(fInjectedProj, ".cpp")

for element in rFiles:
    chosenFile = element.root + "/" + element.file
    regEx = getRegExFromEnum(RegExType.cppVariables)
    listOfMatches = parseFileWithRegEx(regEx, chosenFile)
    contents = getFileContent(chosenFile)
    injectionData = getRandomDataToInject(listOfMatches, RegExType.cppVariables)
    if (injectionData != 0):
        maliciousFile = createMaliciousFile(contents, injectionData.line, injectionData.data)
        writeMaliciousFile(chosenFile, maliciousFile)

        for x in listOfMatches:
            logging.info(" L: %d (C: %s T: %s V: %s)" % (x[0], x[1][0], x[1][1],x[1][2]))

        compilePath = findFirstFile(fInjectedProj, "Makefile").root
        changeDir(compilePath)
        compileRunAndSaveLog(fInjectedProj, fInjectedLogPath)
        writeMaliciousFile(chosenFile, contents)

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

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
from collections import namedtuple, defaultdict
from enum import Enum #To list regEx types

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

failedPayload = [ "#include \"tlm.h\"\n", \
                  "static tlm::tlm_generic_payload *dummy_trr = new tlm::tlm_generic_payload;\n", \
                  "bool run() {\n", \
                      "dummy_trr->set_address(10);\n", \
                      "dummy_trr->set_data_length(10);\n", \
                      "dummy_trr->set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);\n",
                      "return true;\n",
                  "}\n",
                  "bool bla = run();\n"]

walkReturn = namedtuple('walkReturn', 'root, file')
data = namedtuple('data', 'line, var, type')
fault = namedtuple('fault', 'line, data, var')
class RegExType(Enum):
    CPPVariables = 1
    TLMPayload   = 2

class MakeRunStatus(Enum):
    CompilationFailed = 1
    ExecutionFailed   = 2
    ExecutionSucceded = 3
    ExecutionTimeout  = 4
    FileOutputFailed  = 5


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
        logging.error("Failed to compile")
        return MakeRunStatus.CompilationFailed

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
            logging.warning("Failed to use file")
            return MakeRunStatus.FileOutputFailed
    except subprocess.TimeoutExpired:
        logging.info("Process ended with timeout")
        return MakeRunStatus.ExecutionTimeout
    except subprocess.CalledProcessError:
        logging.error("Failed to run")
        return MakeRunStatus.ExecutionFailed
    logging.info("Execution Succesful")
    return MakeRunStatus.ExecutionSucceded

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
def createMaliciousFile(original, injectedContent, category):
    contents = copy.deepcopy(original)
    if (category == RegExType.CPPVariables):
        line = injectedContent.line
        if re.search('\{', contents[line]):
            line += 1
        contents.insert(line, injectedContent.data)
        maliciousFile = []
        maliciousFile.extend(randomBool)
        maliciousFile.extend(contents)
    elif (category == RegExType.TLMPayload):
        line = injectedContent.line - 1
        contents[line] = re.sub('\*', '', contents[line]) #Removes first dereference
        contents[line] = re.sub(str(injectedContent.var), injectedContent.data, contents[line]) #Replace var with fault injected version
        maliciousFile = []
        maliciousFile.extend(randomBool)
        maliciousFile.extend(failedPayload)
        maliciousFile.extend(contents)
    logging.info(" Inserting: %s into line %s" % (injectedContent.data, str(line)))
    return maliciousFile

# Overwrite a file with the malicious code
def writeMaliciousFile(path, maliciousFile):
    with open(path,'w') as f:
        f.writelines(maliciousFile)

# Returns a regular expression given an enum value
def getRegExFromEnum(category):
    if (category == RegExType.CPPVariables):
        regEx = re.compile( #To match any variable declaration/definition
                '(const |[^A-Za-z])'
                '(bigint|int|float|short|char|bool|double'      #C++ types
                '|sc_(?:bit|logic|int|uint|bigint|biguint))'    #SystemC types
                '(?:\<\w*\>)?'                                  #Support bigint templates
                '(?:[ \*&] *\*{0,2}&{0,1} *)'                   #Skip *&' '
                '([A-Z_a-z]\w*)'                                #Variable name
                '[ ,;\)\[\]]')                                  #Ending in =);,[]
        return regEx
    elif (category == RegExType.TLMPayload):
        regEx = re.compile( #To find TLM communications
                 '(?:->)'                                       # Finds operation
                 '(?:nb_transport_[bf]w|(?:b_transport))'       # Matches transport types
                 ' *\( *\* *'                                   # Skip delimiters
                 '([A-Z_a-z]\w*)'                               # Get Payload
                 '[$ ,\n]')                                     # End matching
        return regEx

# Parses matches to choose data to inject
def getRandomDataToInject(listOfMatches, category):
    logging.debug(listOfMatches)
    if (len(listOfMatches) > 0):
        i = 0
        chooseV = False
        if (category == RegExType.CPPVariables):
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
            return fault(rData.line, injectedContent, 0)
        if (category == RegExType.TLMPayload):
            i = random.randint(0, len(listOfMatches) -1)
            injectedContent = "randomBool() ? *dummy_trr:*{0}".format(listOfMatches[i][1][0])
            return fault(listOfMatches[i][0], injectedContent, listOfMatches[i][1][0])
    else:
        return 0

# Returns next valid data to inject
def getDataToInject(listOfMatches, i, category):
    chooseV = False
    logging.debug(listOfMatches)
    if (category == RegExType.CPPVariables):
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
        return fault(rData.line, injectedContent, 0)
    if (category == RegExType.TLMPayload):
        if (len(listOfMatches) > 0 and len(listOfMatches) < i):
            injectedContent = "randomBool() ? *dummy_trr:*{0}".format(listOfMatches[i][1][0])
            return fault(listOfMatches[i][0], injectedContent, listOfMatches[i][1][0])
        else:
            return 0

#### Main Script ####
logging.basicConfig(stream=sys.stderr, level=logging.CRITICAL)
executionStatus = defaultdict(list)
chosenProject = "at_1_phase"
path = "/home/tuliolinux/Downloads/systemc-2.3.1/examples/tlm-seg/"
chosenProject = "fft_fxpt"
cleanLogPath = "/tmp/cleanBuildLog"
fInjectedLogPath = "/tmp/fInjectedBuildLog"
diffPath = "/tmp/diff"
sysCProjs = ['dpipe', 'fft_flpt', 'fft_fxpt', 'fir', 'forkjoin', 'pipe', 'pkt_switch', 'reset_signal_ls', 'risc_cpu', 'rsa', 'sc_export', 'sc_report', 'sc_rvd', 'sc_ttd', 'scx_barrier', 'scx_mutex_w_policy', 'simple_bus', 'simple_fifo', 'simple_perf', 'specialized_signals']
tlmProjs = ['at_1_phase', 'at_2_phase', 'at_4_phase', 'at_extension_optional', 'at_mixed_targets', 'at_ooo', 'lt', 'lt_dmi', 'lt_extension_mandatory', 'lt_mixed_endian', 'lt_temporal_decouple']

for proj in sysCProjs: 
    path = "/home/tuliolinux/Downloads/systemc-2.3.1/examples/sysc/"
    chosenProject = proj
    fullPath = path+chosenProject
    fInjectedProj = path+"fij"
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
    cat = RegExType.TLMPayload
    cat = RegExType.CPPVariables

    for element in rFiles:
        chosenFile = element.root + "/" + element.file
        regEx = getRegExFromEnum(cat)
        listOfMatches = parseFileWithRegEx(regEx, chosenFile)
        contents = getFileContent(chosenFile)
        injectionData = getRandomDataToInject(listOfMatches, cat)
        if (injectionData != 0):
            maliciousFile = createMaliciousFile(contents, injectionData, cat)
            writeMaliciousFile(chosenFile, maliciousFile)

            for x in listOfMatches:
                if (cat == RegExType.CPPVariables):
                    logging.info(" L: %d (C: %s T: %s V: %s)" % (x[0], x[1][0], x[1][1],x[1][2]))
                elif (cat == RegExType.TLMPayload):
                    logging.info(" L: %d (V: %s)" % (x[0], x[1][0]))

            compilePath = findFirstFile(fInjectedProj, "Makefile").root
            changeDir(compilePath)
            executionStatus[chosenProject].append(compileRunAndSaveLog(fInjectedProj, fInjectedLogPath))
        writeMaliciousFile(chosenFile, contents)

# Make diff
comparison = filecmp.cmp(cleanLogPath, fInjectedLogPath)
try:
    f = open(diffPath,'w')
    f.write(str(comparison))
    f.close()
except OSError:
    logging.error("Failed to use file")

# Cleanup routines, delete logs and folders
cleanEnv("Program ran successfully")

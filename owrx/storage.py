from owrx.config.core import CoreConfig
from owrx.config import Config
from datetime import datetime

import threading
import subprocess
import os
import re

import logging

logger = logging.getLogger(__name__)

class Storage(object):
    sharedInstance = None
    creationLock = threading.Lock()
    filePattern = r'[A-Z0-9]+-[0-9]+-[0-9]+(-[0-9]+)?(-[0-9]+)?\.(bmp|png|txt|mp3)'

    # Get shared instance of Storage class
    @staticmethod
    def getSharedInstance():
        with Storage.creationLock:
            if Storage.sharedInstance is None:
                Storage.sharedInstance = Storage()
        return Storage.sharedInstance

    # Construct an instance of Storage class
    def __init__(self):
        self.lock = threading.Lock()

    # Create stored file by name, modifying the name if the file exists
    def newFile(self, fileName: str, buffering: int = -1):
        filePath = self.getFilePath(fileName)

        with self.lock:
            if not os.path.exists(filePath):
                return open(filePath, "wb", buffering = buffering)
            elif "." in filePath:
                filePathX = "-{0}.".join(filePath.rsplit(".", 1))
                for i in range(99):
                    filePath1 = filePathX.format(i + 1)
                    if not os.path.exists(filePath1):
                        return open(filePath1, "wb", buffering = buffering)

        raise FileExistsError("File '{0}' already exists.".format(filePath))

    # Delete stored file by name, the name must match pattern
    def deleteFile(self, fileName: str):
        if re.match(self.filePattern, fileName):
            filePath = self.getFilePath(fileName)
            logger.info("Deleting '{0}'.".format(filePath))
            with self.lock:
                try:
                    os.unlink(filePath)
                except Exception as e:
                    logger.debug("deleteFile(): " + str(e))

    # Get list of stored files, sorted in reverse alphabetic order
    # (so that newer files appear first)
    def getStoredFiles(self):
        dir = CoreConfig().get_temporary_directory()
        with self.lock:
            files = [os.path.join(dir, f) for f in os.listdir(dir) if re.match(self.filePattern, f)]
        files.sort(key=lambda x: os.path.getctime(x), reverse=True)
        return [os.path.basename(f) for f in files]

    # Delete all stored files except for <keep_files> newest ones
    def cleanStoredFiles(self):
        pm    = Config.get()
        keep  = pm["keep_files"]
        dir   = CoreConfig().get_temporary_directory()

        with self.lock:
            files = [os.path.join(dir, f) for f in os.listdir(dir) if re.match(self.filePattern, f)]
            files.sort(key=lambda x: os.path.getctime(x), reverse=True)

            for f in files[keep:]:
                logger.debug("Deleting stored file '%s'." % os.path.basename(f))
                try:
                    os.unlink(f)
                except Exception as e:
                    logger.debug("cleanStoredFiles(): " + str(e))

    # Get file name pattern
    @staticmethod
    def getNamePattern():
        return Storage.filePattern

    # Get complete path to a stored file from its filename by
    # adding folder name
    @staticmethod
    def getFilePath(filename: str):
        return os.path.join(CoreConfig().get_temporary_directory(), filename)

    # Create stored file name by inserting current UTC date
    # and time into the pattern spot designated with "{0}"
    @staticmethod
    def makeFileName(pattern: str = '{0}', frequency: int = 0):
        d = datetime.utcnow().strftime('%y%m%d-%H%M%S')
        f = ('-%d' % (frequency // 1000)) if frequency>0 else ''
        return pattern.format(d + f)

    # Convert given file from BMP to PNG format using ImageMagick
    @staticmethod
    def convertImage(inFile: str):
        # Adds storage path
        if not inFile.startswith('/'):
            inFile = self.getFilePath(inFile)
        # Only converting BMP files for now
        outFile = re.sub(r'\.bmp$', '.png', inFile)
        if outFile==inFile:
            return
        try:
            # Use ImageMagick to convert file
            params = ['convert', inFile, outFile]
            subprocess.check_call(params)
            # If conversion was successful, delete original file
            os.unlink(inFile)
        except Exception as e:
            logger.debug("convertImage(): " + str(e))

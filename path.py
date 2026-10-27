"""
extended versions of standard os.path tools that seamlessly work with
shortcuts
"""
import os
from linkShortcut.windowsLnkFormat import finalPath


def abspath(path):
    """
    Just like os.path.abspath() except it also accounts for shortcuts
    """
    return finalPath(path,True)


def isdir(path):
    """
    Just like os.path.isdir() except it also accounts for shortcuts
    """
    return os.path.isdir(finalPath(path))


def isfile(path):
    """
    Just like os.path.isfile() except it also accounts for shortcuts
    """
    return os.path.isfile(finalPath(path))


def exists(path):
    """
    Just like os.path.exists() except it also accounts for shortcuts
    """
    return os.path.exists(finalPath(path))
"""
extended versions of standard os.path tools that seamlessly work with
shortcuts
"""
import os
from linkShortcut.windowsLnkFormat import finalPath


def abspath(path:str)->str:
    """
    Just like os.path.abspath() except it also accounts for shortcuts

    :param path: the path to resolve
    """
    return finalPath(path,True)


def isdir(path:str)->bool:
    """
    Just like os.path.isdir() except it also accounts for shortcuts

    :param path: the path to check
    """
    return os.path.isdir(finalPath(path))


def isfile(path:str)->bool:
    """
    Just like os.path.isfile() except it also accounts for shortcuts

    :param path: the path to check
    """
    return os.path.isfile(finalPath(path))


def exists(path:str)->bool:
    """
    Just like os.path.exists() except it also accounts for shortcuts

    :param path: the path to check
    """
    return os.path.exists(finalPath(path))
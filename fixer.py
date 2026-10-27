#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Tools to fix links including:
    * broken links / auto-locate targets
    * cleaning up "x - Shortcut" nonsense
    * ... more?
"""
import typing
import os
import winshell # type: ignore
from .findReplace import findAll
from .linkTypes import (
    LINKTYPE_ANY,LINKTYPE_SHORTCUT,LINKTYPE_FOLDER_SHORTCUT,LINKTYPE_NONLINK)


def findBrokenShortcuts(
    path:str,
    recursive:bool=True
    )->typing.Iterable[typing.Tuple[str,str]]:
    """
    This is a generator, so you probably want to do like:
        for link,path in findBrokenShortcuts(...):

    :param path: where to start searching for shortcuts
    :param recursive: True/False whether to search sub-directories
    """
    linkFinderGenerator=findAll(
        path,files=False,links=True,recursive=recursive)
    for sc in linkFinderGenerator:
        sc=winshell.shortcut(sc) # type: ignore
        if (not os.path.isdir(sc.path)) and (not os.path.isfile(sc.path)): # type: ignore # noqa: E501
            yield sc.lnk_filepath,sc.path # type: ignore


def _detectRenamedBranch(
    path:str,
    sep:typing.Optional[str]=None
    )->typing.Optional[str]:
    """
    For each level in path, detect if there is a one-off name difference
        /foo/bar/myfile => /foo/baz/myfile
    or an extra layer
        /foo/bar/myfile => foo/simprini/bar/myfile

    Either returns a corrected path, or None if it couldn't find a fix

    :param path: the broken path
    :param sep: path separator (default os.sep)
    """
    if sep is None:
        sep=os.sep
    print('for "'+path+'"')
    pathParts=path.split(sep)
    for i in range(0,len(pathParts)-1):
        path_idx=len(pathParts)-i-2
        if path_idx<=0:
            break
        pre=sep.join(pathParts[0:path_idx])
        post=sep.join(pathParts[path_idx+1:])
        print('\t'+pre+sep+'???'+sep+post)
        try:
            for d in os.listdir(pre):
                if not os.path.isdir(d):
                    continue
                test=pre+sep+d+sep+post
                print('\t\ttesting "'+test+'"')
                if os.path.isfile(test) or os.path.isdir(test):
                    return test
        except Exception as e:
            print('\t\t'+(str(e).strip()))
        post=sep.join(pathParts[path_idx:])
        print('\t'+pre+sep+'???'+sep+post)
        try:
            for d in os.listdir(pre):
                if not os.path.isdir(d):
                    continue
                test=pre+sep+d+sep+post
                print('\t\ttesting "'+test+'"')
                if os.path.isfile(test) or os.path.isdir(test):
                    return test
        except Exception as e:
            print('\t\t'+(str(e).strip()))
    return None


def _findMissingLevel(
    path:str,
    sep:typing.Optional[str]=None
    )->typing.Optional[str]:
    """
    Find at which point a path goes missing

    :param path: the path to check
    :param sep: path separator (default os.sep)
    """
    if sep is None:
        sep=os.sep
    pathParts=path.split(sep)
    for i in range(len(pathParts)): # TODO: reverse search may be more efficient # noqa: E501
        p=sep.join(pathParts[0:i+1])
        if not (os.path.isdir(p) or os.path.isfile(p)):
            return p
    return None


_findItemsDirCache:typing.Dict[str,typing.List[str]]={}
def _findItems(
    start:str,
    itemName:str,
    sep:typing.Optional[str]=None
    )->typing.Iterator[str]:
    """
    Generator returns all occourances

    :param start: directory to start searching from
    :param itemName: file/directory name to look for
    :param sep: path separator (default os.sep)
    """
    if sep is None:
        sep=os.sep
    search=[start]
    while search:
        s=search.pop(0)
        try:
            if s not in _findItemsDirCache:
                _findItemsDirCache[s]=[s+sep+i for i in os.listdir(s)]
        except Exception:
            _findItemsDirCache[s]=[]
        for f in _findItemsDirCache[s]:
            if f.rsplit(sep,1)[-1]==itemName:
                yield f
            if os.path.isdir(f):
                search.append(f)


def _findBestItem(
    start:str,
    itemPath:str,
    sep:typing.Optional[str]=None
    )->typing.Optional[str]:
    """
    returns the item that best maches the itemPath

    :param start: directory to start searching from
    :param itemPath: the path to find a best match for
    :param sep: path separator (default os.sep)
    """
    if sep is None:
        sep=os.sep
    pathParts=itemPath.split(sep)
    bestScore=0
    bestMatch=None
    print('\tSearching for',pathParts[-1],'in',start)
    for found in _findItems(start,pathParts[-1],sep):
        foundPath=found.split(sep)
        score=0
        for d in pathParts:
            if d in foundPath:
                score=score+1
        print(score,found)
        if score>bestScore:
            bestMatch=found
            bestScore=score
    return bestMatch


def fixBrokenShortcuts(
    path:str,
    recursive:bool=True,
    dryRun:bool=False
    )->None:
    """
    Attempt to find and fix broken shortcuts by twiddling the path

    :param path: where to start searching for shortcuts
    :param recursive: True/False whether to search sub-directories
    :param dryRun: True/False only report what would change
    """
    found=0
    fixed=0
    for _,target in findBrokenShortcuts(path,recursive):
        found=found+1
        if target.find('\\art\\')>=0 or target.find('Program Files')>=0: # for now # noqa: E501
            continue
        print('Fixing: "'+target+'"')
        missing=_findMissingLevel(target)
        print(f'\tLost at: "{missing}"')
        if missing is None:
            z=None
        else:
            z=_findBestItem(missing.rsplit('\\',1)[0],target)
        if z is not None:
            print(f'\tFound: "{z}"')
            fixed=fixed+1
            continue
        if False:
            z=_detectRenamedBranch(target)
            if z is not None:
                print('DETECTED:')
                print('\t'+target)
                print('\t\twas renamed to')
                print('\t'+z)
                fixed=fixed+1
                break
    print('\n(',fixed,'/',found,') broken links fixed')


def printBrokenShortcuts(path:str,recursive:bool=True)->None:
    """
    print(a list of broken shortcuts)

    :param path: where to start searching for shortcuts
    :param recursive: True/False whether to search sub-directories
    """
    i=0
    for k,v in findBrokenShortcuts(path,recursive):
        i=i+1
        print(k+' => '+v)
    print('\n',i,'broken links found')


def cleanupShortcuts(
    searchPaths:typing.Union[str,typing.Iterable[str]],
    recursive:bool=False,
    sanitize:bool=False,
    toFolderShortcuts:bool=False,
    undoFolderShortcuts:bool=False,
    ignorePaths:typing.Optional[typing.Iterable[str]]=None,
    dry:bool=False,
    useGlob:bool=False
    )->None:
    """
    Utility to clean up all shorcuts in folder(s)

    :param searchPaths: directories/files to clean up all shortcuts in
    :param recursive: perform this operation on subdirectories as well
    :param sanitize: remove all "Shortcut To X" and "X - Shortcut" markers
    :param toFolderShortcuts: convert shortcuts to folders into actual
        "folder shortcuts"
    :param undoFolderShortcuts: convert "folder shortcuts" to regular shortcuts
    :param ignorePaths: paths to skip
    :param dry: perform a dry run without destroying anything
    :param useGlob: treat searchPaths as glob expressions (default=False)
    """
    for lnk in findAll(
        searchPaths,
        directories=False,
        files=False,
        links=LINKTYPE_ANY,
        recursive=True,
        useGlob=useGlob
        ):
        #
        if lnk.linkType==LINKTYPE_SHORTCUT:
            if lnk.isDirectory and toFolderShortcuts:
                lnk.changeType(LINKTYPE_FOLDER_SHORTCUT,dry=dry)
            elif sanitize:
                lnk.sanitize()
        elif lnk.linkType==LINKTYPE_NONLINK and recursive and lnk.isDirectory:
            for f in os.listdir(lnk.targetPath):
                cleanupShortcuts(
                    os.path.join(lnk.targetPath,f),
                    recursive,sanitize,toFolderShortcuts=toFolderShortcuts,
                    undoFolderShortcuts=undoFolderShortcuts,
                    dry=dry,ignorePaths=ignorePaths)
        elif lnk.linkType==LINKTYPE_FOLDER_SHORTCUT and undoFolderShortcuts:
            lnk.changeType(LINKTYPE_SHORTCUT,dry=dry)


def cmdline(args:typing.Iterable[str])->int:
    """
    Run the command line

    :param args: command line arguments (WITHOUT the filename)
    """
    files:typing.List[str]=[]
    recursive=False
    sanitize=False
    toFolderShortcuts=False
    undoFolderShortcuts=False
    ignorePaths=None
    dry=False
    useGlob=True
    printhelp=False
    if not args:
        printhelp=True
    else:
        for arg in args:
            if arg.startswith('-'):
                arg=[a.strip() for a in arg.split('=',1)]
                arg[0]=arg[0].lower()
                if arg[0] in ['-h','--help']:
                    printhelp=True
                elif arg[0] in ('-r','--recursive'):
                    recursive=len(arg)<2 \
                        or (arg[1][0].lower() in ('t','y','1'))
                elif arg[0] in ('-s','--sanitize'):
                    sanitize=len(arg)<2 \
                        or (arg[1][0].lower() in ('t','y','1'))
                elif arg[0] in ('-t','--toFolderShortcuts'):
                    toFolderShortcuts=len(arg)<2 \
                        or (arg[1][0].lower() in ('t','y','1'))
                elif arg[0] in ('-u','--undoFolderShortcuts'):
                    undoFolderShortcuts=len(arg)<2 \
                        or (arg[1][0].lower() in ('t','y','1'))
                elif arg[0] in ('-d','--dry'):
                    dry=len(arg)<2 \
                        or (arg[1][0].lower() in ('t','y','1'))
                elif arg[0] in ('-g','--useGlob'):
                    dry=len(arg)<2 \
                        or (arg[1][0].lower() in ('t','y','1'))
                else:
                    print('ERR: unknown argument "'+arg[0]+'"')
                    printhelp=True
                    break
            else:
                files.append(arg)
                break
    if not printhelp:
        if not files:
            print('ERR: No files specified.')
        else:
            cleanupShortcuts(files,recursive,sanitize,toFolderShortcuts,
                undoFolderShortcuts,ignorePaths,dry,useGlob)
    else:
        print('About:')
        print('   Cleans up a series of shortcuts.')
        print('Usage:')
        print('   fixer.py [options] files')
        print('Options:')
        print('   -R --recursive[=t/f] .... make a recursive fix (default=f)')
        print('   -S --sanitize[=t/f] ....  get rid of "shortcut to X" and "X - Shortcut" nonsense (default=t)') # noqa: E501
        print('   -T --toFolderShortcuts[=t/f] . convert shortcuts to folders into "folder shortcuts" (default=f)') # noqa: E501
        print('   -U --undoFolderShortcuts[=t/f] . convert "folder shortcuts" back to regular shortcuts') # noqa: E501
        print('   -G --useGlob[=t/f] ...... treat files as globs (eg "*.lnk") (default=t)') # noqa: E501
        print('   -D --dry[=t/f] .......... perform dry-run, not changing anything (default=f)') # noqa: E501
        return 1
    return 0


if __name__=='__main__':
    import sys
    sys.exit(cmdline(sys.argv[1:]))

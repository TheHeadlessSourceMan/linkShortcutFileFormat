#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Tools to fix links including:
    * broken links / auto-locate targets
    * cleaning up "x - Shortcut" nonsense
    * ... more?
"""
import os
from linkShortcut.linkTypes import *
from linkShortcut.windowsLinks import *
from linkShortcut.findReplace import *


def findBrokenShortcuts(path,recursive=True):
    """
    This is a generator, so you probably want to do like:
        for link,path in findBrokenShortcuts(...):
    """
    linkFinderGenerator=findAll(path,yeild_files=False,yeild_shortcuts=True,recursive=recursive)
    for sc in linkFinderGenerator:
        sc=winshell.shortcut(sc)
        if (not os.path.isdir(sc.path)) and (not os.path.isfile(sc.path)):
            yield sc.lnk_filepath,sc.path


def _detectRenamedBranch(path,sep=None):
    """
    For each level in path, detect if there is a one-off name difference
        /foo/bar/myfile => /foo/baz/myfile
    or an extra layer
        /foo/bar/myfile => foo/simprini/bar/myfile

    Either returns a corrected path, or None if it couldn't find a fix
    """
    if sep is None:
        sep=os.sep
    print('for "'+path+'"')
    path=path.split(sep)
    for i in range(0,len(path)-1):
        path_idx=len(path)-i-2
        if path_idx<=0:
            break
        pre=sep.join(path[0:path_idx])
        post=sep.join(path[path_idx+1:])
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
        post=sep.join(path[path_idx:])
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


def _findMissingLevel(path,sep=None):
    """
    Find at which point a path goes missing
    """
    if sep is None:
        sep=os.sep
    path=path.split(sep)
    for i in range(len(path)): # TODO: reverse search may be more efficient
        p=sep.join(path[0:i+1])
        if not (os.path.isdir(p) or os.path.isfile(p)):
            return p
    return None


_findItemsDirCache={}
def _findItems(start,itemName,sep=None):
    """
    Generator returns all occourances
    """
    if sep is None:
        sep=os.sep
    results=[]
    search=[start]
    while search:
        s=search.pop(0)
        try:
            if s not in _findItemsDirCache:
                _findItemsDirCache[s]=[s+sep+i for i in os.listdir(s)]
        except:
            _findItemsDirCache[s]=[]
        for f in _findItemsDirCache[s]:
            if f.rsplit(sep,1)[-1]==itemName:
                yield f
            if os.path.isdir(f):
                search.append(f)


def _findBestItem(start,itemPath,sep=None):
    """
    returns the item that best maches the itemPath
    """
    if sep is None:
        sep=os.sep
    itemPath=itemPath.split(sep)
    bestScore=0
    bestMatch=None
    print('\tSearching for',itemPath[-1],'in',start)
    for found in _findItems(start,itemPath[-1],sep):
        foundPath=sep.split(found)
        score=0
        for d in itemPath:
            if d in foundPath:
                score=score+1
        print(score,found)
        if score>bestScore:
            bestMatch=found
            bestScore=score
    return bestMatch


def fixBrokenShortcuts(path,recursive=True,dryRun=False):
    """
    Attempt to find and fix broken shortcuts by twiddling the path
    """
    found=0
    fixed=0
    for link,target in findBrokenShortcuts(path,recursive):
        found=found+1
        if target.find('\\art\\')>=0 or target.find('Program Files')>=0: # for now
            continue
        print('Fixing: "'+target+'"')
        missing=_findMissingLevel(target)
        print('\tLost at: "'+missing+'"')
        z=_findBestItem(missing.rsplit('\\',1)[0],target)
        if z is not None:
            print('\tFound: "'+z+'"')
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


def printBrokenShortcuts(path,recursive=True):
    """
    print(a list of broken shortcuts)
    """
    i=0
    for k,v in findBrokenShortcuts(path,recursive):
        i=i+1
        print(k+' => '+v)
    print('\n',i,'broken links found')


def cleanupShortcuts(searchPaths,recursive=False,sanitize=False,toFolderShortcuts=False,undoFolderShortcuts=False,ignorePaths=None,dry=False,useGlob=False):
    """
    Utility to clean up all shorcuts in folder(s)

    :param searchPaths: directories/files to clean up all shortcuts in
    :param recursive: perform this operation on subdirectories as well
    :param sanitize: remove all "Shortcut To X" and "X - Shortcut" markers
    :param toFolderShortcuts: convert shortcuts to folders into actual "folder shortcuts"
    :param undoFolderShortcuts: convert "folder shortcuts" to regular shortcuts
    :param dry: perform a dry run without destroying anything
    :param useGlob: treat searchPaths as glob expressions (default=False)
    """
    for l in findAll(searchPaths,directories=False,files=False,links=LINKTYPE_ANY,recursive=True,useGlob=useGlob):
        if l.linkType==LINKTYPE_SHORTCUT:
            if l.isDirectory and toFolderShortcuts:
                l.changeType(LINKTYPE_FOLDER_SHORTCUT,dry=dry)
            elif sanitize:
                l.sanitize()
        elif l.linkType==LINKTYPE_NONLINK and recursive and l.isDirectory:
            cleanupShortcuts(f,recursive,sanitize,dry=dry,ignorePaths=ignorePaths)
        elif l.linkType==LINKTYPE_FOLDER_SHORTCUT and undoFolderShortcuts:
            l.changeType(LINKTYPE_SHORTCUT,dry=dry)


def cmdline(args):
    """
    Run the command line

    :param args: command line arguments (WITHOUT the filename)
    """
    printhelp=False
    if not args:
        printhelp=True
    else:
        recursive=False
        sanitize=False
        toFolderShortcuts=False
        undoFolderShortcuts=False
        ignorePaths=None
        dry=False
        useGlob=True
        files=[]
        for arg in args:
            if arg.startswith('-'):
                arg=[a.strip() for a in arg.split('=',1)]
                arg[0]=arg[0].lower()
                if arg[0] in ['-h','--help']:
                    printhelp=True
                elif arg[0] in ('-r','--recursive'):
                    recursive=len(arg)<2 or (arg[1][0].lower() in ('t','y','1'))
                elif arg[0] in ('-s','--sanitize'):
                    sanitize=len(arg)<2 or (arg[1][0].lower() in ('t','y','1'))
                elif arg[0] in ('-t','--toFolderShortcuts'):
                    toFolderShortcuts=len(arg)<2 or (arg[1][0].lower() in ('t','y','1'))
                elif arg[0] in ('-u','--undoFolderShortcuts'):
                    undoFolderShortcuts=len(arg)<2 or (arg[1][0].lower() in ('t','y','1'))
                elif arg[0] in ('-d','--dry'):
                    dry=len(arg)<2 or (arg[1][0].lower() in ('t','y','1'))
                elif arg[0] in ('-g','--useGlob'):
                    dry=len(arg)<2 or (arg[1][0].lower() in ('t','y','1'))
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
        print('   -S --sanitize[=t/f] ....  get rid of "shortcut to X" and "X - Shortcut" nonsense (default=t)')
        print('   -T --toFolderShortcuts[=t/f] . convert shortcuts to folders into "folder shortcuts" (default=f)')
        print('   -U --undoFolderShortcuts[=t/f] . convert "folder shortcuts" back to regular shortcuts')
        print('   -G --useGlob[=t/f] ...... treat files as globs (eg "*.lnk") (default=t)')
        print('   -D --dry[=t/f] .......... perform dry-run, not changing anything (default=f)')


if __name__=='__main__':
    import sys
    cmdline(sys.argv[1:])
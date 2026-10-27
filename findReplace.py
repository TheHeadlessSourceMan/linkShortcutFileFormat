#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Tools for searching for files.

It allows advanced things like following links, regular expression
and glob searching, etc.
"""
import os
import sys
import re

from linkShortcut.windowsLinks import *
from linkShortcut.linkTypes import *

MATCH_TYPE_EXACT_TEXT=0;
MATCH_TYPE_GLOB=1;
MATCH_TYPE_REGEX=2;
MATCH_TYPES=['exact text','glob','regex']


def glob2re(glob,ignoreCase=True):
    """
    Converts a command line "glob" expression (e.g. "*.txt") into a full-fledged
    regular expression.

    :param glob: a glob expression
    :param ignoreCase:  True/False make it non-case sensitive (default True / non-case-sensitive)

    :return: a compiled Regex object
    """
    flags=re.DOTALL
    if ignoreCase:
        flags=flags|re.IGNORECASE
    specials=['[',']','.','(',')','{','}','?','+','\\']
    match_re=[]
    for c in glob:
        if c in specials:
            match_re.append('\\'+c)
        elif c=='*':
            match_re.append('.*')
        else:
            match_re.append(c)
    match_re=re.compile(''.join(match_re),flags)


def findAll(startPaths,match=None,matchType=MATCH_TYPE_GLOB,ignoreCase=True,directories=False,files=True,links=False,recursive=True,ignore=None,useGlob=False):
    """
    A smarter os.walk()

    NOTE: this is a width-first traversal

    NOTE: this is an iterator/generator for fast-exit of search loops

    :param startPaths: where to start searching from can be a single path or a list of them
    :param match: what to search for.  If None, then return everything regardless of name.
        If this is not a string/Regex, then it will be converted to a string.
    :param matchType: How to treat the match parameter.  One of MATCH_TYPES.  Default is MATCH_TYPE_GLOB.
        If match is a Regex object, this will always auto-change to MATCH_TYPE_REGEX
    :param ignoreCase:  True/False make it non-case sensitive (default True / non-case-sensitive)
    :param directories: True/False whether to return matching directories
    :param files: True/False whether to return matching files
    :param links: True/False/LINK_TYPES whether to return matching links, and potentially search for a specific link type
        links=True is the same as saying links=LINKTYPE_ANY
    :param recursive: True/False whether to recursively search sub-directories (and links to directories)
    :param ignore: specific files/directories to ignore
    :param useGlob: treat startPaths as glob expressions
    """
    if not isinstance(startPaths,(list,set,tuple)):
        startPaths=(startPaths)
    links=LinkTypeOf(links)
    # make sure we have an ignore list as a set
    if ignore is None:
        ignore=set()
    elif not isinstance(ignore,set):
        ignore=set(ignore)
    # get the match as a regular expression
    if not match:
        match=None
    if match is not None:
        flags=re.DOTALL
        if ignoreCase:
            flags=flags|re.IGNORECASE
        if hasattr(match,'finditer'): # duck-typing for Regex objects
            pass
        elif matchType==MATCH_TYPE_EXACT_TEXT:
            match=re.compile('*.'+re.escape(str(match)),flags);
        elif matchType==MATCH_TYPE_GLOB:
            match=glob2re(match,ignoreCase)
        elif matchType==MATCH_TYPE_REGEX:
            if not hasattr(match,'finditer'): # duck-typing for Regex objects
                match=re.compile(match,flags)
        else:
            raise Exception('Unknown match type: '+str(matchType))
    # create list of the things to be searched
    dumbStuffIGottaSearch=[]
    if useGlob:
        import glob
        for globExpression in startPaths:
            for path in glob.glob(globExpression):
                if path not in ignore:
                    ignore.add(path)
                    dumbStuffIGottaSearch.append(WindowsLink(path))
    else:
        for path in startPaths:
            path=os.path.abspath(path)
            if path not in ignore:
                ignore.add(path)
                dumbStuffIGottaSearch.append(WindowsLink(path))
    # start searching
    while dumbStuffIGottaSearch:
        currentDir=dumbStuffIGottaSearch.pop(0)
        try:
            children=os.listdir(currentDir.targetPath)
        except Exception as e:
            print('ERR: getting directory listing of:\n  ',currentDir.targetPath,file=sys.stderr)
            #raise e
            continue
        for filename in children:
            path=currentDir.targetPath+os.sep+filename
            if path in ignore:
                continue
            item=WindowsLink(path)
            try:
                if item.isDirectory: # checking this is faster, but could return duplicate files!
                    ignore.add(path)
            except Exception: # skip and keep going if things barf
                continue
            # yield the file if it matches the search criteria
            if item.isLink:
                if links==LINKTYPE_ANY or links==item.linkType:
                    if match is None or match.match(filename):
                        yield item
            elif item.isDirectory:
                if directories and (match is None or match.match(filename)):
                    yield item
            else:
                if files and (match is None or match.match(filename)):
                    yield item
            # add next things to search
            if recursive and item.isDirectory:
                dumbStuffIGottaSearch.append(item)


def refactorShortcuts(path,reFrom,reTo,recursive=False,constrainTo=None,dryRun=False):
    """
    Change shortcuts matching reFrom to reTo
        see regex.sub() https://docs.python.org/2/howto/regex.html#search-and-replace

    Also, like any refactoring tool, be very, very careful!
    There is ample oppoprotunity to do unintended things and make a huge mess!
    Dry run FIRST!!!
    """
    linkFinderGenerator=findAll(path,yeild_files=False,yeild_shortcuts=True,recursive=recursive)
    if constrainTo is None or constrainTo=='': # must at least be in the same drive letter
        constrainTo=path.split('\\',1)[0].upper()
    else:
        constrainTo=constrainTo.split('\\',1)
        constrainTo[0]=constrainTo[0].upper()
        constrainTo='\\'.join(constrainTo)
    if type(reFrom)==str:
        reFrom=re.compile(reFrom)
    for sc in linkFinderGenerator:
        sc=winshell.shortcut(sc)
        fromPath=str(sc.lnk_filepath)
        toPath=str(sc.path)
        if toPath.find(constrainTo)==0: # Make sure this is a path we are allowed to make relative (also verifies that it doesn't start with %CD%)
            newPath,count=reFrom.subn(reTo,toPath)
            if count>0 and toPath!=fromPath:
                print('changing...',fromPath+' => '+toPath)
                print('Changing to:',newPath)
                if not dryRun:
                    sc.path=newPath
                    sc.write()
        else:
            print('skipping:',fromPath+' => '+toPath)
            print('\t(it must start with "'+constrainTo+'")')


def cmdline(args):
    """
    Run the command line

    :param args: command line arguments (WITHOUT the filename)
    """
    printhelp=False
    if not args:
        printhelp=True
    else:
        startPath='.'
        match=None
        matchType=MATCH_TYPE_GLOB
        ignoreCase=True
        directories=False
        files=True
        links=False
        recursive=True
        ignore=[]
        didSomething=False
        for arg in args:
            if arg.startswith('-'):
                arg=[a.strip() for a in arg.split('=',1)]
                arg[0]=arg[0].lower()
                if arg[0] in ['-h','--help']:
                    printhelp=True
                elif arg[0]=='--match=None':
                    didSomething=True
                    a=arg[1][0].lower()
                    if a=='r':
                        matchType=MATCH_TYPE_REGEX
                    if a=='g':
                        matchType=MATCH_TYPE_GLOB
                    else:
                        matchType=MATCH_TYPE_EXACT_TEXT
                elif arg[0]=='--ignoreCase':
                    didSomething=True
                    ignoreCase=arg[1][0] in ('T','t','Y','y','1')
                elif arg[0]=='--directories':
                    didSomething=True
                    directories=arg[1][0] in ('T','t','Y','y','1')
                elif arg[0]=='--files':
                    didSomething=True
                    files=arg[1][0] in ('T','t','Y','y','1')
                elif arg[0]=='--links':
                    didSomething=True
                    links=arg[1]
                elif arg[0]=='--recursive':
                    didSomething=True
                    recursive=arg[1][0] in ('T','t','Y','y','1')
                elif arg[0]=='--ignore':
                    didSomething=True
                    ignore.append(arg[1])
                else:
                    print('ERR: unknown argument "'+arg[0]+'"')
            else:
                didSomething=True
                if match is None:
                    match=arg
                else:
                    match=match+' '+arg
        if not didSomething:
            print('ERR: Did not do anything')
            printhelp=True
        else:
            for f in findAll(startPath,match,matchType,ignoreCase,directories,files,links,recursive,ignore):
                print(f.path)
    if printhelp:
        print('Usage:')
        print('  findReplace.py [params] match')
        print('Params:')
        print('   --matchType=[exact|glob|regex] .. kind of match to perform (default=glob)')
        print('   --ignoreCase=T/F ................ case-insensitive search (default=True)')
        print('   --directories=T/F ............... return directories (default=False)')
        print('   --files=T/F ..................... return files (default=True)')
        print('   --links=T/F/type ................ return links (default=False)')
        print('   --recursive=T/F ................. do a recursive search (default=True)')
        print('   --ignore=path ................... ignore particular path(s)')


if __name__=='__main__':
    import sys
    cmdline(sys.argv[1:])

#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Tools for searching for files.

It allows advanced things like following links, regular expression
and glob searching, etc.
"""
import typing
import re
from paths import (UrlCompatible,UrlListCompatible,FilePath,asFilePath,
    isUrlCompatible)
from .windowsLinks import WindowsLink
from .linkTypes import LINKTYPE_ANY,LinkTypeOf


MATCH_TYPE_EXACT_TEXT=0
MATCH_TYPE_GLOB=1
MATCH_TYPE_REGEX=2
MATCH_TYPES=['exact text','glob','regex']


def glob2re(glob:str,ignoreCase:bool=True)->typing.Pattern[str]:
    """
    Converts a command line "glob" expression (e.g. "*.txt")
    into a full-fledged regular expression.

    :param glob: a glob expression
    :param ignoreCase:  True/False make it non-case sensitive
        (default True / non-case-sensitive)

    :return: a compiled Regex object
    """
    flags=re.DOTALL
    if ignoreCase:
        flags=flags|re.IGNORECASE
    specials:typing.List[str]=['[',']','.','(',')','{','}','?','+','\\']
    match_re:typing.List[str]=[]
    for c in glob:
        if c in specials:
            match_re.append('\\'+c)
        elif c=='*':
            match_re.append('.*')
        else:
            match_re.append(c)
    return re.compile(''.join(match_re),flags)


def findAll(
    startPaths:UrlListCompatible,
    match:typing.Union[None,str,typing.Pattern[str]]=None,
    matchType:int=MATCH_TYPE_GLOB,
    ignoreCase:bool=True,
    directories:bool=False,
    files:bool=True,
    links:typing.Union[bool,int]=False,
    recursive:bool=True,
    ignore:UrlListCompatible=None,
    useGlob:bool=False
    )->typing.Iterable[WindowsLink]:
    """
    A smarter os.walk()

    NOTE: this is a width-first traversal

    NOTE: this is an iterator/generator for fast-exit of search loops

    :param startPaths: where to start searching from can be a single path
        or a list of them
    :param match: what to search for.  If None, then return everything
        regardless of name.
        If this is not a string/Regex, then it will be converted to a string.
    :param matchType: How to treat the match parameter.  One of MATCH_TYPES.
        Default is MATCH_TYPE_GLOB.
        If match is a Regex object, this will always auto-change to
        MATCH_TYPE_REGEX
    :param ignoreCase:  True/False make it non-case sensitive
        (default True / non-case-sensitive)
    :param directories: True/False whether to return matching directories
    :param files: True/False whether to return matching files
    :param links: True/False/LINK_TYPES whether to return matching links,
        and potentially search for a specific link type
        links=True is the same as saying links=LINKTYPE_ANY
    :param recursive: True/False whether to recursively search
        sub-directories (and links to directories)
    :param ignore: specific files/directories to ignore
    :param useGlob: treat startPaths as glob expressions
    """
    if startPaths is None:
        startPaths=[]
    elif isUrlCompatible(startPaths):
        startPaths=[startPaths] # type: ignore
    startPaths=typing.cast(typing.List[UrlCompatible],startPaths)
    links=LinkTypeOf(links)
    # make sure we have an ignore set (of absolute path strings)
    if ignore is None:
        ignore=[]
    elif isUrlCompatible(ignore):
        ignore=[ignore] # type: ignore
    ignored:typing.Set[str]={
        str(asFilePath(i).absolute()) for i in ignore} # type: ignore
    # get the match as a regular expression
    if not match:
        match=None
    if match is not None and not isinstance(match,re.Pattern):
        flags=re.DOTALL
        if ignoreCase:
            flags=flags|re.IGNORECASE
        if hasattr(match,'finditer'): # duck-typing for Regex objects
            pass
        elif matchType==MATCH_TYPE_EXACT_TEXT:
            match=re.compile('*.'+re.escape(str(match)),flags)
        elif matchType==MATCH_TYPE_GLOB:
            match=glob2re(match,ignoreCase)
        elif matchType==MATCH_TYPE_REGEX:
            if not hasattr(match,'finditer'): # duck-typing for Regex objects
                match=re.compile(match,flags)
        else:
            raise Exception('Unknown match type: '+str(matchType))
    match=typing.cast(typing.Optional[re.Pattern[str]],match)
    # create list of the things to be searched
    dumbStuffIGottaSearch:typing.List[WindowsLink]=[]
    if useGlob:
        import glob
        for globExpression in startPaths:
            for found in glob.glob(str(asFilePath(globExpression))):
                key=str(asFilePath(found).absolute())
                if key not in ignored:
                    ignored.add(key)
                    dumbStuffIGottaSearch.append(WindowsLink(found))
    else:
        for startPath in startPaths:
            startFile=asFilePath(startPath).absolute()
            if str(startFile) not in ignored:
                ignored.add(str(startFile))
                dumbStuffIGottaSearch.append(WindowsLink(startFile))
    # start searching
    while dumbStuffIGottaSearch:
        currentDir=dumbStuffIGottaSearch.pop(0)
        try:
            children=list(currentDir.targetPath.iterdir())
        except Exception: # as e:
            print('ERR: getting directory listing of:\n  ',currentDir.targetPath,file=sys.stderr) # noqa: E501
            #raise e
            continue
        for child in children:
            filename=child.name
            key=str(child)
            if key in ignored:
                continue
            item=WindowsLink(child)
            try:
                if item.isDirectory: # checking this is faster, but could return duplicate files! # noqa: E501
                    ignored.add(key)
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


def showAllShortcuts(path:UrlCompatible,recursive:bool=True)->None:
    """
    Find and display all links

    same as showAllLinks()

    :param path: where to start searching
    :param recursive: True/False whether to search sub-directories
    """
    return showAllLinks(path,recursive)
def showAllLinks(path:UrlCompatible,recursive:bool=True)->None:
    """
    Find and display all links

    :param path: where to start searching
    :param recursive: True/False whether to search sub-directories
    """
    for link in findAll(path,files=False,links=True,recursive=recursive):
        print(f'{link.path} => {link.targetPath}')


def _isUnder(path:FilePath,prefix:FilePath)->bool:
    """
    Is path the same as, or inside of, prefix?
    (the drive letter is not case sensitive)

    :param path: the path to check
    :param prefix: the containing path
    """
    pathParts=path.parts
    prefixParts=prefix.parts
    if len(prefixParts)>len(pathParts) \
        or pathParts[0].lower()!=prefixParts[0].lower():
        return False
    return pathParts[1:len(prefixParts)]==prefixParts[1:]


def refactorShortcuts(
    path:UrlCompatible,
    reFrom:typing.Union[str,typing.Pattern[str]],
    reTo:str,
    recursive:bool=False,
    constrainTo:typing.Optional[UrlCompatible]=None,
    dryRun:bool=False
    )->None:
    """
    Change shortcuts matching reFrom to reTo
        see regex.sub() at
        https://docs.python.org/2/howto/regex.html#search-and-replace

    :param path: where to start searching for shortcuts
    :param reFrom: regular expression (or compiled Regex) to look for
        in the shortcut targets
    :param reTo: replacement text
    :param recursive: True/False whether to search sub-directories
    :param constrainTo: only change targets starting with this path
        (default is the drive of path)
    :param dryRun: True/False only report what would change

    Also, like any refactoring tool, be very, very careful!
    There is ample oppoprotunity to do unintended things and make a huge mess!
    Dry run FIRST!!!
    """
    linkFinderGenerator=findAll(
        path,
        files=False,
        links=True,
        recursive=recursive)
    if constrainTo is None or constrainTo=='': # must at least be in the same drive letter # noqa: E501
        constrainPath=FilePath(asFilePath(path).absolute().parts[0])
    else:
        constrainPath=asFilePath(constrainTo).absolute()
    if isinstance(reFrom,str):
        reFrom=re.compile(reFrom)
    for link in linkFinderGenerator:
        fromPath=link.path
        toPath=link.targetPath
        if _isUnder(toPath,constrainPath):
            newPath,count=reFrom.subn(reTo,str(toPath))
            if count>0 and newPath!=str(toPath):
                print('changing...',fromPath,'=>',toPath)
                print('Changing to:',newPath)
                if not dryRun:
                    link.targetPath=newPath
        else:
            print('skipping:',fromPath,'=>',toPath)
            print('\t(it must start with "'+str(constrainPath)+'")')


def cmdline(args:typing.Iterable[str])->int:
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
        ignore:typing.List[str]=[]
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
                    links=arg[1][0] in ('T','t','Y','y','1')
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
            for f in findAll(
                startPath,
                match,
                matchType,
                ignoreCase,
                directories,
                files,
                links,
                recursive,
                ignore):
                print(f.path)
    if printhelp:
        print('Usage:')
        print('  findReplace.py [params] match')
        print('Params:')
        print('   --matchType=[exact|glob|regex] .. kind of match to perform (default=glob)') # noqa: E501
        print('   --ignoreCase=T/F ................ case-insensitive search (default=True)') # noqa: E501
        print('   --directories=T/F ............... return directories (default=False)') # noqa: E501
        print('   --files=T/F ..................... return files (default=True)') # noqa: E501
        print('   --links=T/F/type ................ return links (default=False)') # noqa: E501
        print('   --recursive=T/F ................. do a recursive search (default=True)') # noqa: E501
        print('   --ignore=path ................... ignore particular path(s)') # noqa: E501
        return 1
    return 0

if __name__=='__main__':
    import sys
    sys.exit(cmdline(sys.argv[1:]))

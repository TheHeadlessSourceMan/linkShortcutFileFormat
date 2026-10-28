#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Useful windows utilities
"""
import typing
import os
import re
from paths import UrlCompatible,FilePath,asFilePath,asFileString

@typing.overload
def osEnquote(path:None)->None:
    ...
@typing.overload
def osEnquote(path:str)->str:
    ...
def osEnquote(path:typing.Optional[str])->typing.Optional[str]:
    """
    Wrap path in quotes if necessary

    :param path: the path to quote
    """
    if not path:
        return path
    if path[0]!='"':
        if path.find(' ')>=0:
            path='"'+path+'"'
    return path


def uncToPath(unc:str,translateForwardSlashes:bool=True)->str:
    """
    translate a unc path into a standard windows path

    :param unc: the unc path
    :param translateForwardSlashes: True/False convert / into \\
    """
    if translateForwardSlashes:
        unc=unc.replace('/','\\')
    if unc.startswith('\\\\.\\'):
        raise Exception('UNC device paths not supported:\n   '+unc)
    if unc.startswith('\\\\?\\'):
        unc=unc[3:]
    return unc


def pathToUnc(path:UrlCompatible,translateForwardSlashes:bool=True)->str:
    """
    translate a file path into a unc path

    :param path: the file path
    :param translateForwardSlashes: True/False convert / into \\
    """
    text=asFileString(path)
    if translateForwardSlashes:
        text=text.replace('/','\\')
    if text.startswith('\\\\.\\') or text.startswith('\\\\?\\'):
        # already a unc path
        return text
    return '\\\\?\\'+str(asFilePath(text).absolute())


def nextAvailableFilename(
    desiredFilename:UrlCompatible,
    ignore:typing.Union[None,UrlCompatible,typing.Iterable[UrlCompatible]]=None
    )->FilePath:
    """
    Given a desired filename, will always return the next unused rendition
    of it.

    First it return the name unchanged if available.

    If not, will return "filename 1.ext", "filename 2.ext" and so on

    :param desiredFilename: the filename that you want to test
    :param ignore: filename(s) to ignore when checking existing files
        this is useful when chosing a name for renaming an existing file
    """
    desired=asFilePath(desiredFilename).absolute()
    ignored:typing.Set[str]=set()
    if ignore is not None:
        if isinstance(ignore,(str,bytes)) or not isinstance(ignore,typing.Iterable): # noqa: E501
            ignore=[ignore] # type: ignore
        ignored={str(asFilePath(i).absolute()) for i in ignore} # type: ignore # noqa: E501
    def isFree(p:FilePath)->bool:
        return str(p) in ignored \
            or not (p.exists() or p.pathlibPath.is_symlink())
    candidate=desired
    if not isFree(candidate):
        first=desired.name.split('.',1)
        extension='.'+first[1] if len(first)>1 else ''
        i=1
        while not isFree(candidate):
            candidate=desired.parent/(first[0]+' '+str(i)+extension)
            i+=1
    return candidate


def fileAttributes(path:UrlCompatible)->int:
    """
    Get the windows file attribute bits of a path (without following links)

    On other operating systems, a best guess is made.

    :param path: the path to inspect
    """
    p=asFilePath(path).pathlibPath
    attrs=getattr(p.lstat(),'st_file_attributes',None)
    if attrs is not None:
        return int(attrs)
    if p.is_symlink():
        return 0x400|(0x10 if p.is_dir() else 0)
    if p.is_dir():
        return 0x10
    return 0x80


def defaultIcon(size:int=32)->typing.Any:
    """
    A generic document icon as a PIL image, for when
    the real icon cannot be extracted (eg. not running on windows)

    :param size: width and height in pixels
    """
    import PIL.Image
    import PIL.ImageDraw
    img=PIL.Image.new('RGBA',(size,size),(0,0,0,0))
    draw=PIL.ImageDraw.Draw(img)
    m=max(size//8,1)
    fold=size//3
    draw.polygon(
        [(m,m),(size-m-fold,m),(size-m,m+fold),(size-m,size-m),(m,size-m)],
        fill=(245,245,245,255),outline=(90,90,90,255))
    draw.polygon(
        [(size-m-fold,m),(size-m-fold,m+fold),(size-m,m+fold)],
        fill=(200,200,200,255),outline=(90,90,90,255))
    return img


def hIconToPIL(hIcon:typing.Any)->typing.Any:
    """
    convert a windows icon handle into
    a useable PIL image

    :param hIcon: windows icon handle
    """
    import win32api
    import win32ui
    import win32gui
    import win32con
    import PIL.Image
    ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
    hdc = win32ui.CreateDCFromHandle(
        win32gui.GetDC(0)) # type: ignore
    hbmp = win32ui.CreateBitmap()
    hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_x)
    hdc = hdc.CreateCompatibleDC()
    hdc.SelectObject(hbmp)
    hdc.DrawIcon((0, 0), hIcon)
    win32gui.DestroyIcon(hIcon) # type: ignore
    bmpinfo = hbmp.GetInfo() # type: ignore
    bmpstr = hbmp.GetBitmapBits(True)
    img = PIL.Image.frombuffer(
        "RGBA",
        (bmpinfo["bmWidth"],bmpinfo["bmHeight"]), # type: ignore
        bmpstr,"raw","BGRA",0,1
        )
    return img


def iconForFiletype(path:UrlCompatible)->typing.Any:
    """
    get a useable PIL image based on a file type

    :param path: file to get the icon for.  NOTE: this file
        doesn't need to actually exist if you want the icon for a type
    """
    try:
        from win32com.shell import shell,shellcon # type: ignore
        from win32con import FILE_ATTRIBUTE_NORMAL
    except ImportError: # not windows, or pywin32 not installed
        return defaultIcon()
    extension='.'+asFilePath(path).extension
    flags=shellcon.SHGFI_SMALLICON | \
        shellcon.SHGFI_ICON | \
        shellcon.SHGFI_USEFILEATTRIBUTES
    try:
        _,info=shell.SHGetFileInfo( # type: ignore
            extension,FILE_ATTRIBUTE_NORMAL,flags)
        return hIconToPIL(info[0]) # type: ignore
    except Exception:
        return defaultIcon()


def iconImage(
    path:typing.Optional[UrlCompatible]='',
    index_sep:typing.Optional[str]=':',
    index_plus_one:bool=True
    )->typing.Any:
    """
    get the icon for a given path.

    :param path: the path can be anything like
            foo.ico
            foo.dll
            foo.dll:34
            foo.exe:34
        also, will find system icons
            moricons.dll:14
            imageres.dll:2
            SHELL32.dll:0 -- hint: this is the default file icon
            :0 -- same as above
            or call with no path at all for the same thing
        (a string may carry the ":index" suffix, other types are just paths)
    :param index_sep: path separator for files with multiple icons
        eg "foo.dll:21" (if None, do not use indexes)
    :param index_plus_one: since windows uses 1 for the first icon,
        this lets us start at 0

    NOTE: makes use of
        https://stackoverflow.com/questions/23263599/how-to-extract-128x128-icon-bitmap-data-from-exe-in-python
    """
    import PIL.Image
    if path is None:
        spec=''
    elif isinstance(path,str):
        spec=path
    else:
        spec=asFileString(path)
    index=0
    if index_sep:
        match=re.match(
            r'^(.*?)(?:'+re.escape(index_sep)+r'(-?[0-9]+))?$',
            spec,re.DOTALL)
        if match is not None:
            spec=match.group(1)
            if match.group(2):
                index=int(match.group(2))
    if index_plus_one:
        index+=1
    sysrootStr=os.environ.get('SystemRoot')
    sysroot=FilePath(sysrootStr) if sysrootStr else None
    iconFile:FilePath
    # make sure it's out there
    if not spec:
        if sysroot is None:
            return defaultIcon()
        iconFile=sysroot/'System32'/'SHELL32.dll'
    else:
        iconFile=asFilePath(spec).expandvars
        if not iconFile.exists():
            if sysroot is None:
                return defaultIcon() # windows system files don't exist here
            if len(iconFile.parts)!=1: # not a bare name, so not a system file # noqa: E501
                raise FileNotFoundError("[Errno 2] No such file or directory: '"+str(iconFile)+"'") # noqa: E501
            for candidate in (sysroot/spec,sysroot/'System32'/spec):
                if candidate.exists():
                    iconFile=candidate
                    break
            else:
                raise FileNotFoundError("[Errno 2] No such file or directory: '"+spec+"'") # noqa: E501
    # if it's an ico file, load it.
    if iconFile.extension=='ico':
        return PIL.Image.open(str(iconFile))
    path=str(iconFile)
    # No?  Okay, load as a dll (only possible with the windows libraries).
    try:
        import win32api
        import win32gui
        import win32ui
        import win32con
    except ImportError: # not windows, or pywin32 not installed
        return defaultIcon()
    try:
        large,small=win32gui.ExtractIconEx(path,index) # type: ignore
        for h in small: # type: ignore
            win32gui.DestroyIcon(h) # type: ignore
        hIcon=large[0] # type: ignore
        ico_x=win32api.GetSystemMetrics(win32con.SM_CXICON)
        ico_y=win32api.GetSystemMetrics(win32con.SM_CYICON)
        hdc=win32ui.CreateDCFromHandle(
            win32gui.GetDC(0)) # type: ignore
        hbmp=win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc,ico_x,ico_y)
        hdc=hdc.CreateCompatibleDC()
        hdc.SelectObject(hbmp)
        hdc.DrawIcon((0,0),hIcon) # type: ignore
        win32gui.DestroyIcon(hIcon) # type: ignore
        bitmapbits=hbmp.GetBitmapBits(True)
    except Exception: # no such icon, or the windows call failed
        return defaultIcon()
    return PIL.Image.frombuffer(
        'RGBA',(ico_x,ico_y),bitmapbits,'raw','BGRA',0,1)


def cmdline(args:typing.Iterable[str])->int:
    """
    Run the command line

    :param args: command line arguments (WITHOUT the filename)
    """
    printhelp=False
    if not args:
        printhelp=True
    else:
        for arg in args:
            if arg.startswith('-'):
                arg=[a.strip() for a in arg.split('=',1)]
                if arg[0] in ['-h','--help']:
                    printhelp=True
                elif arg[0]=='--osEnquote':
                    if len(arg)>1:
                        print(osEnquote(arg[1]))
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--nextAvailableFilename':
                    if len(arg)>1:
                        print(nextAvailableFilename(arg[1]))
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--viewIcon':
                    iconImage(arg[1]).show()
                else:
                    print('ERR: unknown argument "'+arg[0]+'"')
            else:
                print('ERR: unknown argument "'+arg+'"')
    if printhelp:
        print('Usage:')
        print('  windowsUtils.py [options]')
        print('Options:')
        print('   --osEnquote=path ................. test os filename quoting')
        print('   --nextAvailableFilename=path ..... given a filename, get the next available rendition') # noqa: E501
        print('   --viewIcon=path.dll[:index] ...... find and view a given icon') # noqa: E501
        return -1
    return 0


if __name__=='__main__':
    import sys
    sys.exit(cmdline(sys.argv[1:]))

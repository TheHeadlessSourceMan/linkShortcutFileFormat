#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Useful windows utilities
"""
import typing
import os

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


def pathToUnc(path:str,translateForwardSlashes:bool=True)->str:
    """
    translate a file path into a unc path

    :param path: the file path
    :param translateForwardSlashes: True/False convert / into \\
    """
    if translateForwardSlashes:
        path=path.replace('/','\\')
    if path.startswith('\\\\.\\') or path.startswith('\\\\?\\'):
        # already a unc path
        return path
    path='\\\\?\\'+os.path.abspath(path)
    return path


def nextAvailableFilename(
    desiredFilename:str,
    ignore:typing.Union[None,str,typing.Iterable[str]]=None
    )->str:
    """
    Given a desired filename, will always return the next unused rendition
    of it.

    First it return the name unchanged if available.

    If not, will return "filename 1.ext", "filename 2.ext" and so on

    :param desiredFilename: the filename that you want to test
    :param ignore: filename(s) to ignore when checking existing files
        this is useful when chosing a name for renaming an existing file
    """
    desiredFilename=os.path.abspath(desiredFilename)
    while desiredFilename.endswith(os.sep):
        desiredFilename=desiredFilename[0:-1]
    parts=desiredFilename.rsplit(os.sep,1)
    ls=[parts[0]+os.sep+f for f in os.listdir(parts[0])]
    if ignore is not None:
        if isinstance(ignore,str):
            ignore=[ignore]
        for i in ignore:
            i=os.path.abspath(i)
            try:
                ls.remove(i)
            except ValueError:
                continue
    if desiredFilename in ls:
        first=parts[-1].split('.',1)
        if len(first)>1:
            first[1]='.'+first[1]
        else:
            first.append('')
        i=1
        while desiredFilename in ls:
            desiredFilename=os.sep.join([
                parts[0],
                first[0]+' '+str(i)+first[1]])
            i+=1
    return desiredFilename


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


def iconForFiletype(path:str)->typing.Any:
    """
    get a useable PIL image based on a file type

    :param path: file to get the icon for.  NOTE: this file
        doesn't need to actually exist if you want the icon for a type
    """
    from win32com.shell import shell,shellcon # type: ignore
    from win32con import FILE_ATTRIBUTE_NORMAL
    extension='.'+path.rsplit('.',1)[-1]
    flags=shellcon.SHGFI_SMALLICON | \
        shellcon.SHGFI_ICON | \
        shellcon.SHGFI_USEFILEATTRIBUTES
    _,info=shell.SHGetFileInfo( # type: ignore
        extension,FILE_ATTRIBUTE_NORMAL,flags)
    return hIconToPIL(info[0]) # type: ignore


def iconImage(
    path:str='',
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
    :param index_sep: path separator for files with multiple icons
        eg "foo.dll:21" (if None, do not use indexes)
    :param index_plus_one: since windows uses 1 for the first icon,
        this lets us start at 0

    NOTE: makes use of
        https://stackoverflow.com/questions/23263599/how-to-extract-128x128-icon-bitmap-data-from-exe-in-python
    """
    import PIL.Image
    index=0
    if index_sep:
        pathParts:typing.List[str]=path.rsplit(os.sep,1)
        first=pathParts[-1].rsplit(index_sep,1)
        if len(first)>1:
            index=int(first[-1])
        pathParts[-1]=first[0]
        path=os.sep.join(pathParts)
    if index_plus_one:
        index+=1
    # make sure it's out there
    if not path:
        path=os.environ['SystemRoot']+r'\System32\SHELL32.dll'
    elif not os.path.exists(path):
        if path.find(os.sep)<=0: # could be a system file
            sysroot=os.environ['SystemRoot']+os.sep
            if os.path.exists(sysroot+path):
                path=sysroot+path
            elif os.path.exists(sysroot+r'\System32'+os.sep+path):
                path=sysroot+r'\System32'+os.sep+path
            else:
                raise FileNotFoundError("[Errno 2] No such file or directory: '"+path+"'") # noqa: E501
        else:
            raise FileNotFoundError("[Errno 2] No such file or directory: '"+path+"'") # noqa: E501
    # if it's an ico file, load it.
    if path.endswith('.ico'):
        return PIL.Image.open(path)
    # No?  Okay, load as a dll.
    import win32api
    import win32gui
    import win32ui
    import win32con
    large,small=win32gui.ExtractIconEx(path,index) # type: ignore
    win32gui.DestroyIcon(small[0]) # type: ignore
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
    img=PIL.Image.frombuffer('RGBA',(ico_x,ico_y),bitmapbits,'raw','BGRA',0,1)
    return img


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

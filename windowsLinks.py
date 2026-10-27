#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Wraps a windows link file of any kind.

If a proper file is given, will be able to handle it gracefully in most
cases, but beware of what you have before operating on it. (use WindowsLink.isLink())

Also handles special case "Folder Shortcuts" (not the same as a shortcut
to a folder)  For the scoop on that, see:
    https://superuser.com/questions/456399/what-different-types-of-shortcut-are-there/639967#639967
"""
import os
import sys
import subprocess

import pythoncom
from win32com.shell import shell, shellcon
from win32com.storagecon import STGM_READ

from linkShortcut.linkExceptions import *
from linkShortcut.linkTypes import *
from linkShortcut.windowsUtils import *


class WindowsLink:
    """
    Wraps a windows link file of any kind.

    If a proper file is given, will be able to handle it gracefully in most
    cases, but beware of what you have before operating on it. (use WindowsLink.isLink())

    Also handles special case "Folder Shortcuts" (not the same as a shortcut
    to a folder)  For the scoop on that, see:
        https://superuser.com/questions/456399/what-different-types-of-shortcut-are-there/639967#639967
    """

    def __init__(self,path,resolveBroken=False):
        """
        :param path: path to the link we want to inspect
        :param resolveBroken: try to find the target if it has moved (can be slow)

        NOTE:
            https://docs.microsoft.com/en-us/windows/desktop/shell/sfgao
            https://docs.microsoft.com/en-us/windows/desktop/api/Shobjidl_core/nn-shobjidl_core-ishelllinka
        """
        self._path=os.path.abspath(path)
        self._resolveBroken=resolveBroken
        self._targetPath=None
        self._uncPath=None
        self._workingDirectory=None
        self._linkType=LINKTYPE_NONLINK
        self._description=None
        self._iconPath=None
        self._iconIndex=0
        self._isDirectory=False
        self._isZipFile=False
        self._loaded=False

    @property
    def targetPath(self):
        """
        target path location for the link

        If it is not a link, returns the path
        """
        self.refreshInfo(False)
        if self._targetPath is None:
            return self.path
        return os.path.abspath(self._targetPath)
    @targetPath.setter
    def targetPath(self,targetPath):
        """
        target path location for the link
        """
        raise NotImplementedError()

    @property
    def uncPath(self):
        """
        UNC path location for the link
        """
        self.refreshInfo(False)
        return self._uncPath
    @uncPath.setter
    def uncPath(self,uncPath):
        """
        UNC path location for the link
        """
        raise NotImplementedError()

    @property
    def workingDirectory(self):
        """
        working directory for the link
        """
        self.refreshInfo(False)
        return self._workingDirectory
    @workingDirectory.setter
    def workingDirectory(self,workingDirectory):
        """
        working directory for the link
        """
        raise NotImplementedError()

    @property
    def description(self):
        """
        link description
        """
        self.refreshInfo(False)
        return self._description
    @description.setter
    def description(self,description):
        """
        link description
        """
        raise NotImplementedError()

    @property
    def iconPath(self):
        """
        path to the icon file
        """
        self.refreshInfo(False)
        return self._iconPath
    @iconPath.setter
    def iconPath(self,iconPath):
        """
        path to the icon file
        """
        raise NotImplementedError()

    @property
    def iconIndex(self):
        """
        index of the icon within the file
        """
        self.refreshInfo(False)
        return self._iconIndex
    @iconIndex.setter
    def iconIndex(self,iconIndex):
        """
        index of the icon within the file
        """
        raise NotImplementedError()

    @property
    def icon(self):
        """
        get the icon as a PIL image

        can return None
        """
        if self.iconPath is not None:
            from PIL import Image
            return Image.open(self.iconPath)
        return None

    @property
    def isDirectory(self):
        """
        Is the link target a directory (or a file)?
        """
        self.refreshInfo(False)
        if self._isZipFile: # otherwise windows will say, "yes this is a directory"
            return False
        return self._isDirectory

    @property
    def isLink(self):
        """
        Is this a link of some kind (as opposed to a regular file)
        """
        return self.linkType!=LINKTYPE_NONLINK

    @property
    def path(self):
        """
        the path to the link this object points to

        changing this changes the what the object is looking at and
        IS NOT the same thing as rename()
        """
        return self._path
    @path.setter
    def path(self,path):
        self._path=os.path.abspath(path)
        self.refreshInfo(True)

    @property
    def resolveBroken(self):
        """
        Whether to attempt to resolve broken links (can cause slowness)
        """
        return self._resolveBroken
    @resolveBroken.setter
    def resolveBroken(self,resolveBroken):
        self._resolveBroken=resolveBroken
        self.refreshInfo(True)

    def rename(self,newName,dry=False):
        """
        Rename this file/link
        """
        if self.linkType==LINKTYPE_NONLINK:
            newName=os.path.abspath(newName)
            print('changing',LINK_TYPES[self.linkType],'shortcut',osEnquote(self.path))
            print('    into',LINK_TYPES[self.linkType],'shortcut',osEnquote(newName))
            if not dry:
                os.rename(self.path,newName)
                self.path=newName # will force a refresh
        else:
            self._changeShortcut(None,newName,False,dry=dry)

    @property
    def linkType(self):
        """
        Get or change the type of link this is
        """
        self.refreshInfo(False)
        return self._linkType
    @linkType.setter
    def linkType(self,linkType):
        self.changeType(linkType)

    def changeType(self,linkType,dry=False):
        """
        Change the type of link this is

        You can usually just assign linkType, but this is exposed in
        case you want to try a dry run first
        """
        self._changeShortcut(linkType,dry=dry)

    def sanitize(self,dry=False):
        """
        Sanitize the name of this shortcut by removing
            "Shortcut To X" and "X - Shortcut" nonsense
        """
        if self.linkType!=LINKTYPE_NONLINK:
            self._changeShortcut(dry=dry)

    def _changeShortcut(self,newType=None,newPath=None,sanitize=True,dry=False):
        """
        Change a shortcut's type and/or name

        Due to complexity, only applies to shortcuts.  Actual files will error out.
        """
        if newPath is None:
            newPath=self.path
        if self.linkType==LINKTYPE_NONLINK:
            raise LinkException('ERR: Cannot change a file into a link (would result in lost file AND targetless link)')
        if newType is None:
            newType=self.linkType
        if newType==LINKTYPE_NONLINK:
            raise LinkException('ERR: Cannot create a file from a link.  What is that?  A file copy, or what??')
        if newType==LINKTYPE_FOLDER_SHORTCUT:
            if not self.isDirectory:
                raise LinkException('ERR: Cannot create directory shortcut to something that is not a directory!')
        # figure out the new filename
        newPath=self.path
        if newType!=LINKTYPE_SHORTCUT: # strip any .lnk extension(s)
            while newPath.endswith('.lnk'):
                newPath=newPath[0:-4]
        elif newType==LINKTYPE_SHORTCUT: # make sure it has a .lnk extension
            if not newPath.endswith('.lnk'):
                newPath=newPath+'.lnk'
        newPath=nextAvailableFilename(newPath,ignore=self.path)
        if sanitize:
            newPath=self._sanitizedName(newPath)
        # make sure something has changed, or why take action?
        if newPath!=self.path or newType!=self.linkType:
            # delete existing, then create new
            self.deleteLink(dry=dry)
            newLink=WindowsLink.createLink(self.targetPath,newType,newPath,False,dry)
            if not dry:
                self.path=newLink.path # will force a refresh, which is what we want!
                self._linkType=newType

    def _getLinkTarget(self,path):
        return self._getLinkTargetOld(path)

    def _getLinkTargetSlow(self,path):
        """
        cheesy workaround, but it at least works

        scrape the output of a DIR command
        """
        import re
        import subprocess
        target=path
        path=path.rsplit(os.sep,1)
        regex='(?P<month>[0-9]{2})/(?P<day>[0-9]{2})/(?P<year>[0-9]{4})\s+(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2})\s+(?P<ampm>AM|PM)\s{4}((?P<kind><(.*)>)|(\s*(?P<size>[0-9,]+)))\s+(?P<filename>.*)'
        regex=re.compile(regex,re.IGNORECASE|re.DOTALL)
        #cmd='dir /n /r "'+path[0]+'"'
        cmd='dir /al /n /r "'+path[0]+'"' # make a little faster by only asking for symlinks
        out,err=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).communicate()
        out=out.decode('utf-8','ignore').replace('\r','').split('\n')
        for line in out:
            if not line or line[0]==' ':
                continue
            match=regex.match(line)
            if not match.group('kind'):
                #print("Match failed on line\n  ",line)
                continue
            #print('Link kind:\n  ',match.group('kind'))
            if match.group('kind') in ('<SYMLINKD>'):
                filename=match.group('filename').rsplit('[',1)
                link_target=filename[1].rsplit(']',1)[0].strip()
                filename=filename[0].strip()
                if filename==path[1]:
                    self._linkType=LINKTYPE_FOLDER_SHORTCUT
                    target=link_target
                    return target # bail fast
                    #break
        if False: # try again using traditional method instead
            path=os.sep.join(path)
            if target==path:
                # link type/target not specified by dir, but still could be one
                target=self._getLinkTarget(path)
        return target

    def _getLinkTargetNew(self,path):
        """
        another idea that allegedly works, but I haven't seen it
        """
        import win32file
        import win32con
        hFile=win32file.CreateFile(path,
            win32file.GENERIC_READ,
            win32file.FILE_SHARE_READ,
            None,
            win32con.OPEN_EXISTING,
            0x400|0x10, #win32file.FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_DIRECTORY
            #win32file.FILE_ATTRIBUTE_NORMAL,
            None)
        win32file.GetFinalPathNameByHandle(hFile,win32con.VOLUME_NAME_NT)
        win32file.CloseHandle(hFile)

    def _getLinkTargetOld(self,path):
            """
            This did okay, but I couldn't make it work with directory links
            """
            import ctypes
            Msi=ctypes.WinDLL('msi.dll')
            hResult=Msi.MsiGetShortcutTargetW(path,None,None,None)
            if hResult==0:
                # https://stackoverflow.com/questions/32413157/why-in-finding-target-path-of-shortcut-with-shell-link-in-c-it-refers-to-windo
                MAX_PATH=256
                pcchBuf=ctypes.wintypes.LPDWORD(MAX_PATH)
                hResult=Msi.MsiGetComponentPathW(None,None,path,pcchBuf)
                print(hResult)
            else:
                shellLink=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink)
                if self._isDirectory:
                    # print('IID_IPersistStream')
                    persistFile=shellLink.QueryInterface(pythoncom.IID_IPersistStream)
                else:
                    # print('IID_IPersistFile')
                    persistFile=shellLink.QueryInterface(pythoncom.IID_IPersistFile)
                self._linkType=LINKTYPE_SHORTCUT
                if self._isDirectory:
                    self._linkType=LINKTYPE_FOLDER_SHORTCUT
                if True:
                    try:
                        if os.path.exists(path):
                            persistFile.Load(path)
                        else:# os.path.exists(path+'.lnk'):
                            persistFile.Load(path+'.lnk')
                    except Exception as e:
                        #print('WARN: Had trouble inspecting file\n  ',path)
                        #raise e
                        self._linkType=LINKTYPE_NONLINK
                        return path
                #if self.resolveBroken:
                #    shellLink.Resolve(0,shell.SLR_ANY_MATCH|shell.SLR_NO_UI)
                self._targetPath,_=shellLink.GetPath(0)
                self._uncPath=shellLink.GetPath(shell.SLGP_UNCPRIORITY)[0]
            #print('PPP',self._targetPath)
            #print('UUU',self._uncPath)
            shellLink.GetDescription()
            self._workingDirectory=shellLink.GetWorkingDirectory()
            self._iconPath,self._iconIndex=shellLink.GetIconLocation()
            if self._linkType!=LINKTYPE_FOLDER_SHORTCUT:
                self._isDirectory=os.path.isdir(self.targetPath)

    def refreshInfo(self,force=True):
        """
        Called automatically as needed, but you can call
        this manually before an operation if you suspect the
        data may have changed.

        :param force: force the thing to refresh, as opposed to refreshing only
            if _loaded=False
        """
        if self._loaded and not force:
            return
        self._targetPath=None
        self._uncPath=None
        self._workingDirectory=None
        self._linkType=LINKTYPE_NONLINK
        self._description=None
        self._iconPath=None
        self._iconIndex=0
        self._isDirectory=False
        self._isZipFile=False
        self._loaded=True
        if self.path is None:
            return
        path=self.path
        if False:
            desktop=shell.SHGetDesktopFolder()
            try:
                #if path.endswith('.lnk'):
                #    path=path.rsplit('.',1)[0]
                _,pidl,_=desktop.ParseDisplayName(None,None,path)
            except Exception as e:
                print('Path exists?',os.path.exists(path))
                print('   ',path)
                #msg='ERR inspecting '+osEnquote(path)+':\n\t'+str(e)
                #raise LinkException(msg) # TODO: I've found this can be a problem with filenames containing unicode characters
                pidl=SHParseDisplayName(path)
            shell_item =shell.SHCreateShellItem(None,None,pidl)
            attrs=shell_item.GetAttributes(shellcon.SFGAO_STREAM|shellcon.SFGAO_LINK|shellcon.SFGAO_FOLDER)
            self._isDirectory=attrs&shellcon.SFGAO_FOLDER>0
            isLink=attrs&shellcon.SFGAO_LINK>0
            self._isZipFile=(attrs&shellcon.SFGAO_STREAM)>0 and (attrs&shellcon.SFGAO_FOLDER)>0
        if True:
            import win32file
            try:
                # see also:
                #    https://docs.microsoft.com/en-us/windows/desktop/FileIO/file-attribute-constants
                attrs=win32file.GetFileAttributesExW(path)
            except Exception as e:
                print('ERR getting attributes for file:\n  ',path,file=sys.stderr)
                raise e
            attrs=attrs[0]
            self._isDirectory=attrs&0x10>0
            isLink=attrs&0x400>0 or path.lower().endswith('.lnk')
            #print('0x%08x'%attrs,self._isDirectory,path)
        if isLink:
            # windows calls some things links that for our purposes, shouldn't be
            isLink=path.rsplit('.',1)[-1].lower() not in ['url','zip','pif']
        if self._isDirectory:
            path=self._getLinkTargetSlow(path)
        else:
            path=self._getLinkTarget(path)
        return path

    @staticmethod
    def createLink(toLocation,linkType=LINKTYPE_SHORTCUT,shortcutName=None,sanitize=True,dry=False):
        """
        Create a new link/shortcut

        :param toLocation: the destination of the link (can be a file or a UNC path)
        :param linkType: the type of link to create
            by default create a normal shortcut
        :param shortcutName: Name for the new link.  If omitted, make it the same name as the target
        :param sanitize: remove any "Shortcut To X" and "X - Shortcut" nonsense
        :param dry: perform dry run for testing -- don't actually create anything
        """
        if shortcutName is None:
            while True:
                shortcutName=toLocation.rsplit(os.sep,1)[-1]
                if shortcutName!='':
                    break
        if sanitize:
            shortcutName=WindowsLink._sanitizedName(shortcutName)
        shortcutName=nextAvailableFilename(shortcutName)
        shortcutName=pathToUnc(shortcutName)
        if dry:
            print('creating '+LINK_TYPES[linkType]+' link from',shortcutName,'to',toLocation)
        elif linkType==LINKTYPE_SHORTCUT:
            # create using WShell com object.  See also:
            #    https://docs.microsoft.com/en-us/previous-versions//aew9yb99(v=vs.85)
            #    http://www.informit.com/articles/article.aspx?p=1187429&seqNum=5
            if not shortcutName.endswith('.lnk'):
                # add .lnk file extension if necessary
                shortcutName=shortcutName+'.lnk'
            import win32com.client
            ws=win32com.client.Dispatch("WScript.Shell")
            shortcut=ws.CreateShortCut(shortcutName)
            shortcut.Targetpath=toLocation
            #shortcut.WorkingDirectory=
            #shortcut.IconLocation=
            #shortcut.Arguments=
            #shortcut.Description=
            #shortcut.Hotkey=
            #shortcut.WindowStyle=
            shortcut.Save()
        else:
            toLocationUNC=osEnquote(pathToUnc(toLocation))
            if linkType==LINKTYPE_FOLDER_SHORTCUT:
                cmd='mklink /d '+shortcutName+' '+toLocationUNC
            elif linkType==LINKTYPE_JUNCTION:
                cmd='mklink /j '+shortcutName+' '+toLocationUNC
            elif linkType==LINKTYPE_HARD_LINK:
                cmd='mklink /h '+shortcutName+' '+toLocationUNC
            elif linkType==LINKTYPE_SYMBOLIC_LINK:
                cmd='mklink '+shortcutName+' '+toLocationUNC
            else:
                raise LinkException("Cannot create links of type "+str(linkType))
            print(cmd)
            po=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            out,err=po.communicate()
            err=err.decode('utf-8','ignore').strip()
            if err:
                print(cmd)
                raise LinkException("ERR creating link: "+err)
            print(out)
        return WindowsLink(shortcutName)

    def __repr__(self):
        """
        Get a string representation of this link
        """
        self.refreshInfo(False)
        ret=[osEnquote(self.path)]
        ret.append('Type: '+LINK_TYPES[self.linkType])
        if self.targetPath is not None and self.targetPath:
            ret.append('Target: '+osEnquote(self.targetPath))
        if self.uncPath is not None and self.uncPath:
            ret.append('UNC: '+self.uncPath)
        if self.isDirectory is not None:
            ret.append('Is Directory: '+str(self.isDirectory))
        if self.iconPath is not None and self.iconPath:
            ret.append('Icon: '+osEnquote(self.iconPath)+'['+str(self.iconIndex)+']')
        if self.workingDirectory is not None and self.workingDirectory:
            ret.append('Working Directory: '+osEnquote(self.workingDirectory))
        if self.description is not None and self.description:
            ret.append('Description: "'+self.description+'"')
        return '\n   '.join(ret)

    @staticmethod
    def _sanitizedName(path):
        """
        given a path to a shortcut, returns a sanitized name,
        that is, no "Shortcut To myfile" or "myfile - Shortcut"
        """
        shortcutTo='Shortcut To '
        shortcut=' - Shortcut'
        # disassemble
        path=path.rsplit(os.sep,1)
        path[-1]=path[-1].split('.',1)
        # fixup
        if path[-1][0].startswith(shortcutTo):
            path[-1][0]=path[-1][0].rsplit(shortcutTo-1)[-1]
        if path[-1][0].endswith(shortcut):
            path[-1][0]=path[-1][0].split(shortcut,1)[0]
        # reassemble
        path[-1]='.'.join(path[-1])
        return os.sep.join(path)

    def delete(self,dry=False):
        """
        delete whatever kind of file/shortcut this is

        :param dry: perform a dry run without actually deleting anything
        """
        if self.linkType==LINKTYPE_NONLINK:
            if dry:
                print('Will delete shortcut',osEnquote(self.path))
            else:
                os.remove(self.path)
        else:
            self.deleteLink(dry)

    def deleteLink(self,dry=False):
        """
        This will ONLY delete if it's a link.
        If it is an actual file, then raises an exception.

        :param dry: perform a dry run without actually deleting anything

        NOTE: from here on out this object is invalid!
        """
        if not self.isLink:
            raise LinkException('ERR not a shortcut: '+osEnquote(self.path))
        if dry:
            print('Will delete shortcut',osEnquote(self.path))
        else:
            if os.path.isdir(self.path): # folder shortcut
                # turns out there is no need to remove these manually
                #os.remove(path+os.sep+'target.lnk')
                #os.remove(path+os.sep+'desktop.ini')
                os.rmdir(self.path)
            else:
                os.remove(self.path)


def createLink(toLocation,linkType=None,shortcutName=None,sanitize=True,dry=False):
        """
        Create a new link/shortcut
        (shorthand for WindowsLink.createLink)

        :param toLocation: the destination of the link (supports UNC names)
        :param linkType: the type of link to create
            by default create either a normal shortcut or a folder shortcut
        :param shortcutName: Name for the new link.  If omitted, make it the same name as the target
        :param sanitize: remove any "Shortcut To X" and "X - Shortcut" nonsense
        :param dry: perform dry run for testing -- don't actually create anything
        """
        return WindowsLink.createLink(toLocation,linkType,shortcutName,sanitize,dry)


def cmdline(args):
    """
    Run the command line

    :param args: command line arguments (WITHOUT the filename)
    """
    printhelp=False
    if not args:
        printhelp=True
    else:
        dry=False
        for arg in args:
            if arg.startswith('-'):
                arg=[a.strip() for a in arg.split('=',1)]
                if arg[0] in ['-h','--help']:
                    printhelp=True
                elif arg[0]=='-D':
                    dry=True
                elif arg[0]=='--toFolderShortcut':
                    if len(arg)>1:
                        l=WindowsLink(arg[1])
                        l.linkType=LINKTYPE_FOLDER_SHORTCUT
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--toNormalShortcut':
                    if len(arg)>1:
                        l=WindowsLink(arg[1])
                        l.linkType=LINKTYPE_SHORTCUT
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--deleteLink':
                    if len(arg)>1:
                        l=WindowsLink(arg[1])
                        l.deleteLink(dry=dry)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--createShortcut':
                    if len(arg)>1:
                        WindowsLink.createLink(arg[1],1)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--createFolderShortcut':
                    if len(arg)>1:
                        WindowsLink.createLink(arg[1],2)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--createJunction':
                    if len(arg)>1:
                        WindowsLink.createLink(arg[1],3)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--createHardLink':
                    if len(arg)>1:
                        WindowsLink.createLink(arg[1],4)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--createSoftLink':
                    if len(arg)>1:
                        WindowsLink.createLink(arg[1],5)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--shortcutTarget':
                    if len(arg)>1:
                        l=WindowsLink(arg[1])
                        print(l.targetPath)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--isFolderShortcut':
                    if len(arg)>1:
                        l=WindowsLink(arg[1])
                        print(l.linkType==LINKTYPE_FOLDER_SHORTCUT)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--isShortcut':
                    if len(arg)>1:
                        l=WindowsLink(arg[1])
                        print(l.linkType!=LINKTYPE_NONLINK)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--isShortcutToFolder':
                    if len(arg)>1:
                        l=WindowsLink(arg[1])
                        print(l.linkType!=LINKTYPE_NONLINK and l.isDirectory)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                elif arg[0]=='--info':
                    if len(arg)>1:
                        filename=arg[1]
                        l=WindowsLink(filename)
                        print(l)
                    else:
                        print('ERR: no path specified')
                        printhelp=True
                        break
                else:
                    print('ERR: unknown argument "'+arg[0]+'"')
                    printhelp=True
                    break
            else:
                print('ERR: unknown argument "'+arg+'"')
                printhelp=True
                break
    if printhelp:
        print('Usage:')
        print('  windowsLinks.py [options] [commands]')
        print('Options/commands (evaluated IN ORDER!):')
        print('   -D ............................. perform dry-run, not changing anything')
        print('   --toFolderShortcut=path ........ turn a link to folder into a "folder shortcut"')
        print('   --toNormalShortcut=path ........ turn a link, "folder shortcut", etc into a normal shortcut')
        print('   --deleteLink=path .............. delete (only) a link (never the actual file)')
        print('   --createShortcut=target ........ create a regular shortcut link')
        print('   --createFolderShortcut=target .. create a folder shortcut link')
        print('   --createJunction=target ........ create a junction point link')
        print('   --createHardLink=target ........ create a hard link')
        print('   --createSoftLink=target ........ create a soft link')
        print('   --shortcutTarget=path .......... get the target of a link')
        print('   --isFolderShortcut=path ........ is this a "folder link"')
        print('   --isShortcut=path .............. is this any kind of link')
        print('   --isShortcutToFolder=path ...... is this any kind of link to a folder')
        print('   --info=path .................... get info about link')


if __name__=='__main__':
    import sys
    cmdline(sys.argv[1:])

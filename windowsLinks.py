#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Wraps a windows link file of any kind.

If a proper file is given, will be able to handle it gracefully in most
cases, but beware of what you have before operating on it.
(use WindowsLink.isLink())

Shortcuts are read and written directly in the binary .lnk format, and
symbolic/hard links go through the standard library, so no windows
libraries are required.

Also handles special case "Folder Shortcuts" (not the same as a shortcut
to a folder)  For the scoop on that, see:
    https://superuser.com/questions/456399/what-different-types-of-shortcut-are-there/639967#639967
"""
import typing
import os
import subprocess
from paths import UrlCompatible,FilePath,asFilePath
from .linkExceptions import LinkException,RecursiveLinkException
from .windowsUtils import osEnquote,nextAvailableFilename,fileAttributes
from .windowsLnkFormat import WindowsLnkFormat
from .linkTypes import (LINK_TYPES,
    LINKTYPE_SHORTCUT,LINKTYPE_NONLINK,LINKTYPE_FOLDER_SHORTCUT,
    LINKTYPE_JUNCTION,LINKTYPE_HARD_LINK,LINKTYPE_SYMBOLIC_LINK)


_FOLDER_SHORTCUT_CLSID='{0AFACED1-E828-11D1-9187-B532F1E9575D}'
_FOLDER_SHORTCUT_TARGET='target.lnk'
_FOLDER_SHORTCUT_INI='desktop.ini'


def _lexists(path:FilePath)->bool:
    """
    Does this exist (including broken symlinks)?

    :param path: the path to check
    """
    return bool(path.exists()) or path.pathlibPath.is_symlink()


def _folderShortcutTarget(path:FilePath)->typing.Optional[FilePath]:
    """
    If path is a "folder shortcut", return the file holding its
    target (otherwise None)

    :param path: the directory to inspect
    """
    lnk=path/_FOLDER_SHORTCUT_TARGET
    ini=path/_FOLDER_SHORTCUT_INI
    if not (lnk.is_file() and ini.is_file()):
        return None
    data=ini.pathlibPath.read_bytes()
    for encoding in ('utf-16','utf-8','cp1252'):
        try:
            text=data.decode(encoding)
            break
        except UnicodeError:
            continue
    else:
        return None
    if _FOLDER_SHORTCUT_CLSID.lower() in text.lower():
        return lnk
    return None


def _winAttrib(path:FilePath,flags:typing.Sequence[str])->None:
    """
    Set attributes (eg. '+s') using the windows attrib command.
    Does nothing on other operating systems.

    :param path: file or directory
    :param flags: attrib flags
    """
    if os.name=='nt':
        subprocess.run(['attrib',*flags,str(path)],check=False,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


class WindowsLink:
    """
    Wraps a windows link file of any kind.

    If a proper file is given, will be able to handle it gracefully in most
    cases, but beware of what you have before operating on it.
    (use WindowsLink.isLink())

    Also handles special case "Folder Shortcuts" (not the same as a shortcut
    to a folder)  For the scoop on that, see:
        https://superuser.com/questions/456399/what-different-types-of-shortcut-are-there/639967#639967

    NOTE: FilePath's == operator recurses forever, so compare paths
    using str() instead.
    """

    def __init__(self,path:UrlCompatible,resolveBroken:bool=False):
        """
        :param path: path to the link we want to inspect
        :param resolveBroken: try to find the target if it has moved
            (can be slow)
        """
        self._path:FilePath=asFilePath(path).absolute()
        self._resolveBroken:bool=resolveBroken
        self._targetPath:typing.Optional[FilePath]=None # non-shortcut links
        self._lnk:typing.Optional[WindowsLnkFormat]=None
        self._lnkFile:typing.Optional[FilePath]=None
        self._linkType:int=LINKTYPE_NONLINK
        self._isDirectory:bool=False
        self._loaded:bool=False

    def _editShortcut(self,
        edit:typing.Callable[[WindowsLnkFormat],None]
        )->None:
        """
        Change the underlying .lnk data and save it

        :param edit: function that modifies the loaded lnk data
        """
        self.refreshInfo(False)
        if self._lnk is None or self._lnkFile is None:
            raise LinkException('ERR: only shortcuts can be edited: '+str(self.path)) # noqa: E501
        edit(self._lnk)
        self._lnk.save(self._lnkFile,noClobberFile=False)
        self.refreshInfo(True)

    @staticmethod
    def _targetInfo(target:UrlCompatible)->typing.Tuple[bool,int]:
        """
        (is a directory, file size) of a link target on disk

        :param target: the target path
        """
        p=asFilePath(target)
        size=p.pathlibPath.stat().st_size if p.is_file() else 0
        return p.isDirectory,size

    def _setTarget(self,target:UrlCompatible)->None:
        """
        Point the shortcut at a new target

        :param target: the new target path
        """
        info=WindowsLink._targetInfo(target)
        self._editShortcut(lambda k:k.setTarget(target,*info))

    @property
    def targetPath(self)->FilePath:
        """
        target path location for the link

        If it is not a link, returns the path
        """
        self.refreshInfo(False)
        target=self._targetPath
        if self._lnk is not None:
            target=self._lnk.getTarget()
        if target is None:
            return self.path
        return target.absolute()
    @targetPath.setter
    def targetPath(self,targetPath:UrlCompatible)->None:
        """
        target path location for the link (shortcuts only)

        :param targetPath: the new target
        """
        self._setTarget(targetPath)

    @property
    def uncPath(self)->typing.Optional[str]:
        """
        UNC path location for the link
        """
        self.refreshInfo(False)
        if self._lnk is None:
            return None
        return self._lnk.uncPath
    @uncPath.setter
    def uncPath(self,uncPath:str)->None:
        """
        UNC path location for the link (shortcuts only)

        :param uncPath: the new UNC path
        """
        self._setTarget(uncPath)

    @property
    def workingDirectory(self)->typing.Optional[FilePath]:
        """
        working directory for the link
        """
        self.refreshInfo(False)
        if self._lnk is None or not self._lnk.workingDirectory:
            return None
        return FilePath(self._lnk.workingDirectory)
    @workingDirectory.setter
    def workingDirectory(self,workingDirectory:UrlCompatible)->None:
        """
        working directory for the link (shortcuts only)

        :param workingDirectory: the new working directory
        """
        text=str(asFilePath(workingDirectory))
        self._editShortcut(lambda s:setattr(s,'workingDirectory',text))

    @property
    def description(self)->typing.Optional[str]:
        """
        link description
        """
        self.refreshInfo(False)
        if self._lnk is None:
            return None
        return self._lnk.description
    @description.setter
    def description(self,description:str)->None:
        """
        link description (shortcuts only)

        :param description: the new description
        """
        self._editShortcut(lambda s:setattr(s,'description',description))

    @property
    def iconPath(self)->typing.Optional[str]:
        """
        path to the icon file (as stored, so it may contain %variables%)
        """
        self.refreshInfo(False)
        if self._lnk is None:
            return None
        return self._lnk.iconFile
    @iconPath.setter
    def iconPath(self,iconPath:str)->None:
        """
        path to the icon file (shortcuts only)

        :param iconPath: the new icon path
        """
        self._editShortcut(lambda s:setattr(s,'iconFile',iconPath))

    @property
    def iconIndex(self)->int:
        """
        index of the icon within the file
        """
        self.refreshInfo(False)
        if self._lnk is None:
            return 0
        return self._lnk.iconNumber
    @iconIndex.setter
    def iconIndex(self,iconIndex:int)->None:
        """
        index of the icon within the file (shortcuts only)

        :param iconIndex: the new icon index
        """
        self._editShortcut(lambda s:setattr(s,'iconNumber',iconIndex))

    @property
    def hotKey(self)->int:
        """
        raw hotkey value (low byte=virtual key, high byte=modifiers)
        """
        self.refreshInfo(False)
        if self._lnk is None:
            return 0
        return self._lnk.hotKey
    @hotKey.setter
    def hotKey(self,hotKey:int)->None:
        """
        raw hotkey value (shortcuts only)

        :param hotKey: the new hotkey
        """
        self._editShortcut(lambda s:setattr(s,'hotKey',hotKey))

    @property
    def icon(self)->typing.Optional[typing.Any]:
        """
        get the icon as a PIL image

        can return None if the link has no custom icon.
        If the icon cannot be extracted on this operating system,
        a default image is returned.
        """
        if self.iconPath:
            from .windowsUtils import iconImage
            return iconImage(
                self.iconPath+':'+str(self.iconIndex),index_plus_one=False)
        return None

    @property
    def isDirectory(self)->bool:
        """
        Is the link target a directory (or a file)?
        """
        self.refreshInfo(False)
        return self._isDirectory

    @property
    def isLink(self)->bool:
        """
        Is this a link of some kind (as opposed to a regular file)
        """
        return self.linkType!=LINKTYPE_NONLINK

    @property
    def path(self)->FilePath:
        """
        the path to the link this object points to

        changing this changes the what the object is looking at and
        IS NOT the same thing as rename()
        """
        return self._path
    @path.setter
    def path(self,path:UrlCompatible)->None:
        """
        Point this object at a different link

        :param path: path to the new link
        """
        self._path=asFilePath(path).absolute()
        self.refreshInfo(True)

    @property
    def resolveBroken(self)->bool:
        """
        Whether to attempt to resolve broken links (can cause slowness)
        """
        return self._resolveBroken
    @resolveBroken.setter
    def resolveBroken(self,resolveBroken:bool)->None:
        """
        Whether to attempt to resolve broken links (can cause slowness)

        :param resolveBroken: True/False
        """
        self._resolveBroken=resolveBroken
        self.refreshInfo(True)

    def rename(self,newName:UrlCompatible,dry:bool=False)->None:
        """
        Rename this file/link

        :param newName: the new path/name
        :param dry: perform a dry run without actually renaming anything
        """
        if self.linkType==LINKTYPE_NONLINK:
            newPath=asFilePath(newName).absolute()
            print('changing',LINK_TYPES[self.linkType],'shortcut',osEnquote(str(self.path))) # noqa: E501
            print('    into',LINK_TYPES[self.linkType],'shortcut',osEnquote(str(newPath))) # noqa: E501
            if not dry:
                self.path.pathlibPath.rename(newPath.pathlibPath)
                self.path=newPath # will force a refresh
        else:
            self._changeShortcut(None,newName,False,dry=dry)

    @property
    def linkType(self)->int:
        """
        Get or change the type of link this is
        """
        self.refreshInfo(False)
        return self._linkType
    @linkType.setter
    def linkType(self,linkType:int)->None:
        """
        Change the type of link this is

        :param linkType: one of the LINKTYPE_* constants
        """
        self.changeType(linkType)

    def changeType(self,linkType:int,dry:bool=False)->None:
        """
        Change the type of link this is

        You can usually just assign linkType, but this is exposed in
        case you want to try a dry run first

        :param linkType: one of the LINKTYPE_* constants
        :param dry: perform a dry run without changing anything
        """
        self._changeShortcut(linkType,dry=dry)

    def sanitize(self,dry:bool=False)->None:
        """
        Sanitize the name of this shortcut by removing
            "Shortcut To X" and "X - Shortcut" nonsense

        :param dry: perform a dry run without changing anything
        """
        if self.linkType!=LINKTYPE_NONLINK:
            self._changeShortcut(dry=dry)

    def _changeShortcut(self,
        newType:typing.Optional[int]=None,
        newPath:typing.Optional[UrlCompatible]=None,
        sanitize:bool=True,
        dry:bool=False
        )->None:
        """
        Change a shortcut's type and/or name

        Due to complexity, only applies to shortcuts.  Actual files
        will error out.

        :param newType: new link type (default is to keep the current type)
        :param newPath: new path (default is to keep the current path)
        :param sanitize: remove any "Shortcut To X" and "X - Shortcut" nonsense
        :param dry: perform a dry run without changing anything
        """
        newName=str(self.path if newPath is None else asFilePath(newPath))
        if self.linkType==LINKTYPE_NONLINK:
            raise LinkException('ERR: Cannot change a file into a link (would result in lost file AND targetless link)') # noqa: E501
        if newType is None:
            newType=self.linkType
        if newType==LINKTYPE_NONLINK:
            raise LinkException('ERR: Cannot create a file from a link.  What is that?  A file copy, or what??') # noqa: E501
        if newType==LINKTYPE_FOLDER_SHORTCUT:
            if not self.isDirectory:
                raise LinkException('ERR: Cannot create directory shortcut to something that is not a directory!') # noqa: E501
        # figure out the new filename
        if newType!=LINKTYPE_SHORTCUT: # strip any .lnk extension(s)
            while newName.endswith('.lnk'):
                newName=newName[0:-4]
        elif not newName.endswith('.lnk'): # make sure it has a .lnk extension
            newName=newName+'.lnk'
        newPath=nextAvailableFilename(newName,ignore=self.path)
        if sanitize:
            newPath=self._sanitizedName(newPath)
        # make sure something has changed, or why take action?
        if str(newPath)!=str(self.path) or newType!=self.linkType:
            target=self.targetPath
            # delete existing, then create new
            self.deleteLink(dry=dry)
            newLink=WindowsLink.createLink(target,newType,newPath,False,dry)
            if not dry and newLink is not None:
                self.path=newLink.path # will force a refresh, which is what we want! # noqa: E501

    def refreshInfo(self,force:bool=True)->None:
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
        self._lnk=None
        self._lnkFile=None
        self._linkType=LINKTYPE_NONLINK
        self._isDirectory=False
        self._loaded=True
        path=self._path
        withExtension=FilePath(str(path)+'.lnk')
        if not _lexists(path) and _lexists(withExtension):
            path=withExtension
            self._path=path
        try:
            attrs=fileAttributes(path)
        except OSError:
            return # nonexistent, so not a link
        isDir=attrs&0x10>0
        isSymlink=path.pathlibPath.is_symlink()
        lnkFile:typing.Optional[FilePath]=None
        if isDir:
            lnkFile=_folderShortcutTarget(path)
            if lnkFile is not None:
                self._linkType=LINKTYPE_FOLDER_SHORTCUT
            elif isSymlink:
                self._linkType=LINKTYPE_SYMBOLIC_LINK
            elif attrs&0x400>0:
                self._linkType=LINKTYPE_JUNCTION
        elif WindowsLnkFormat.isShortcut(path):
            lnkFile=path
            self._linkType=LINKTYPE_SHORTCUT
        elif isSymlink:
            self._linkType=LINKTYPE_SYMBOLIC_LINK
        if lnkFile is not None:
            self._lnkFile=lnkFile
            self._lnk=WindowsLnkFormat(lnkFile)
            target=self._lnk.getTarget()
            if self._linkType==LINKTYPE_FOLDER_SHORTCUT:
                self._isDirectory=True
            elif target is not None and target.exists():
                self._isDirectory=target.isDirectory
            else:
                self._isDirectory=self._lnk.fileAttr.targetIsDir
        elif self._linkType!=LINKTYPE_NONLINK:
            # resolve() follows symlinks and junctions
            self._targetPath=FilePath(str(path.pathlibPath.resolve()))
            self._isDirectory=isDir
        else:
            self._isDirectory=isDir

    @staticmethod
    def createLink(
        toLocation:typing.Optional[UrlCompatible],
        linkType:typing.Optional[int]=LINKTYPE_SHORTCUT,
        shortcutName:typing.Optional[UrlCompatible]=None,
        sanitize:bool=True,
        dry:bool=False
        )->typing.Optional['WindowsLink']:
        """
        Create a new link/shortcut

        :param toLocation: the destination of the link
            (can be a file or a UNC path)
        :param linkType: the type of link to create
            by default create a normal shortcut
        :param shortcutName: Name for the new link.
            If omitted, make it the same name as the target
        :param sanitize: remove any "Shortcut To X" and "X - Shortcut" nonsense
        :param dry: perform dry run for testing -- aka, don't actually
            create anything
        """
        if linkType is None:
            linkType=LINKTYPE_SHORTCUT
        if toLocation is None:
            raise LinkException("Cannot create link without a target location")
        target=asFilePath(toLocation)
        if shortcutName is None:
            shortcutName=FilePath(target.name)
        newPath=asFilePath(shortcutName).absolute()
        if sanitize:
            newPath=WindowsLink._sanitizedName(newPath)
        if linkType==LINKTYPE_SHORTCUT and newPath.extension!='lnk':
            newPath=FilePath(str(newPath)+'.lnk')
        newPath=nextAvailableFilename(newPath)
        if dry:
            print('creating '+LINK_TYPES[linkType]+' link from',newPath,'to',target) # noqa: E501
            return None
        if linkType==LINKTYPE_SHORTCUT:
            lnk=WindowsLnkFormat()
            lnk.setTarget(toLocation,*WindowsLink._targetInfo(toLocation))
            lnk.save(newPath,noClobberFile=False)
        elif linkType==LINKTYPE_FOLDER_SHORTCUT:
            newPath.pathlibPath.mkdir()
            lnk=WindowsLnkFormat()
            lnk.setTarget(toLocation,*WindowsLink._targetInfo(toLocation))
            lnk.save(newPath/_FOLDER_SHORTCUT_TARGET,noClobberFile=False)
            ini=newPath/_FOLDER_SHORTCUT_INI
            ini.pathlibPath.write_bytes(('[.ShellClassInfo]\r\nCLSID2='\
                +_FOLDER_SHORTCUT_CLSID+'\r\nFlags=2\r\n').encode('utf-16'))
            _winAttrib(ini,['+s','+h'])
            _winAttrib(newPath,['+r']) # the shell needs this to honor desktop.ini # noqa: E501
        elif linkType==LINKTYPE_SYMBOLIC_LINK:
            newPath.symlink_to(target,target.isDirectory)
        elif linkType==LINKTYPE_HARD_LINK:
            os.link(str(target),str(newPath))
        elif linkType==LINKTYPE_JUNCTION:
            if os.name!='nt':
                raise LinkException('ERR: Junctions only exist on windows')
            result=subprocess.run(
                ['cmd','/c','mklink','/j',str(newPath),str(target)],
                capture_output=True,check=False)
            if result.returncode!=0:
                err=result.stderr.decode('utf-8','ignore').strip()
                raise LinkException('ERR creating link: '+err)
        else:
            raise LinkException("Cannot create links of type "+str(linkType))
        return WindowsLink(newPath)

    def __repr__(self)->str:
        """
        Get a string representation of this link
        """
        self.refreshInfo(False)
        ret:typing.List[str]=[str(osEnquote(str(self.path)))]
        ret.append('Type: '+LINK_TYPES[self.linkType])
        ret.append('Target: '+str(osEnquote(str(self.targetPath))))
        if self.uncPath:
            ret.append('UNC: '+self.uncPath)
        ret.append('Is Directory: '+str(self.isDirectory))
        if self.iconPath:
            ret.append('Icon: '+str(osEnquote(self.iconPath))\
                +'['+str(self.iconIndex)+']')
        if self.workingDirectory is not None:
            ret.append('Working Directory: '\
                +str(osEnquote(str(self.workingDirectory))))
        if self.description:
            ret.append('Description: "'+self.description+'"')
        return '\n   '.join(ret)

    @staticmethod
    def _sanitizedName(path:UrlCompatible)->FilePath:
        """
        given a path to a shortcut, returns a sanitized name,
        that is, no "Shortcut To myfile" or "myfile - Shortcut"

        :param path: path to the shortcut
        """
        shortcutTo='Shortcut To '
        shortcut=' - Shortcut'
        p=asFilePath(path).absolute()
        nameParts=p.name.split('.',1)
        if nameParts[0].startswith(shortcutTo):
            nameParts[0]=nameParts[0].rsplit(shortcutTo,1)[-1]
        if nameParts[0].endswith(shortcut):
            nameParts[0]=nameParts[0].split(shortcut,1)[0]
        return p.parent/'.'.join(nameParts)

    def delete(self,dry:bool=False)->None:
        """
        delete whatever kind of file/shortcut this is

        :param dry: perform a dry run without actually deleting anything
        """
        if self.linkType==LINKTYPE_NONLINK:
            if dry:
                print('Will delete',osEnquote(str(self.path)))
            else:
                self.path.remove()
        else:
            self.deleteLink(dry)

    def deleteLink(self,dry:bool=False)->None:
        """
        This will ONLY delete if it's a link.
        If it is an actual file, then raises an exception.

        :param dry: perform a dry run without actually deleting anything

        NOTE: from here on out this object is invalid!
        """
        if not self.isLink:
            raise LinkException('ERR not a shortcut: '+str(self.path))
        if dry:
            print('Will delete shortcut',osEnquote(str(self.path)))
        elif self.linkType==LINKTYPE_FOLDER_SHORTCUT:
            for name in (_FOLDER_SHORTCUT_TARGET,_FOLDER_SHORTCUT_INI):
                f=self.path/name
                f.pathlibPath.chmod(0o666)
                f.remove()
            self.path.pathlibPath.chmod(0o777)
            self.path.remove()
        else: # file, or directory symlink/junction
            self.path.remove()


def createLink(
    toLocation:UrlCompatible,
    linkType:typing.Optional[int]=None,
    shortcutName:typing.Optional[UrlCompatible]=None,
    sanitize:bool=True,
    dry:bool=False
    )->typing.Optional[WindowsLink]:
    """
    Create a new link/shortcut
    (shorthand for WindowsLink.createLink)

    :param toLocation: the destination of the link (supports UNC names)
    :param linkType: the type of link to create
        by default create a normal shortcut
    :param shortcutName: Name for the new link.
        If omitted, make it the same name as the target
    :param sanitize: remove any "Shortcut To X" and "X - Shortcut" nonsense
    :param dry: perform dry run for testing -- don't actually create anything
    """
    return WindowsLink.createLink(
        toLocation,linkType,shortcutName,sanitize,dry)


def createShortcut(
    inDir:UrlCompatible,
    target:UrlCompatible,
    name:typing.Optional[str]=None,
    description:typing.Optional[str]=None,
    icon:typing.Optional[str]=None,
    hotkey:typing.Optional[int]=None
    )->WindowsLink:
    """
    Create a .lnk file

    :param inDir: directory to create the shortcut in
    :param target: what the shortcut points to
    :param name: name of the shortcut (default is the target's name)
    :param description: shortcut description
    :param icon: icon location
    :param hotkey: raw shortcut hotkey value
    """
    if name is None:
        name=asFilePath(target).name
    link=WindowsLink.createLink(
        target,LINKTYPE_SHORTCUT,asFilePath(inDir)/name,False)
    assert link is not None
    if description is not None:
        link.description=description
    if icon is not None:
        link.iconPath=icon
    if hotkey is not None:
        link.hotKey=hotkey
    return link


def finalPath(path:UrlCompatible,absolute:bool=False)->FilePath:
    """
    Returns either the path given, or if it's a link, the path it points to

    * Will follow link-to-a-links

    Could raise RecursiveLinkException

    :param path: the path to resolve
    :param absolute: True/False return the result as an absolute path
    """
    followed:typing.List[str]=[]
    current=asFilePath(path)
    while True:
        absolutePath=str(current.absolute())
        if absolutePath in followed:
            followed.append(absolutePath)
            raise RecursiveLinkException(followed)
        followed.append(absolutePath)
        link=WindowsLink(current)
        if not link.isLink or str(link.targetPath)==str(link.path):
            break
        current=link.targetPath
    if absolute:
        return current.absolute()
    return current

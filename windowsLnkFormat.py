#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Manually reads/writes the windows lnk file format

Therefore, unlike WindowsLink objects, this is os-independent!
"""
import typing
import struct
import os
from .linkExceptions import NotALinkException,RecursiveLinkException
from .linkTypes import (
    LINKTYPE_HARD,LINKTYPE_SHORTCUT,LINKTYPE_JUNCTION,LINKTYPE_SYMBOLIC,
    LINKTYPE_SYMBOLIC_LINK)


class _WindowsShortcutFileAttr:
    """
    The file attribute flags of a shortcut's target
    """
    def __init__(self,attrDword:typing.Optional[int]=None)->None:
        """
        :param attrDword: attribute bits to initialize from
        """
        self.targetIsReadonly=False
        self.targetIsHidden=False
        self.targetIsSysFile=False
        self.targetIsVolume=False
        self.targetIsDir=False
        self.targetNeedsBackup=False
        self.targetIsEncrypted=False
        self.targetIsNormal=False
        self.targetIsTempfile=False
        self.targetIsSparse=False
        self.targetHasReparse=False
        self.targetIsCompressed=False
        self.targetIsOffline=False
        if attrDword is not None:
            self.set(attrDword)

    def set(self,attrDword:int)->None:
        """
        Set the attributes from a bit field

        :param attrDword: attribute bits
        """
        self.targetIsReadonly=attrDword&0x0001>0
        self.targetIsHidden=attrDword&0x0002>0
        self.targetIsSysFile=attrDword&0x0004>0
        self.targetIsVolume=attrDword&0x0008>0
        self.targetIsDir=attrDword&0x0010>0
        self.targetNeedsBackup=attrDword&0x0020>0
        self.targetIsEncrypted=attrDword&0x0040>0
        self.targetIsNormal=attrDword&0x0080>0
        self.targetIsTempfile=attrDword&0x0100>0
        self.targetIsSparse=attrDword&0x0200>0
        self.targetHasReparse=attrDword&0x0400>0
        self.targetIsCompressed=attrDword&0x0600>0
        self.targetIsOffline=attrDword&0x0800>0

    def __int__(self)->int:
        """
        The attributes as a bit field
        """
        return self.get()
    def get(self)->int:
        """
        Get the attributes as a bit field
        """
        result=0x0000
        if self.targetIsReadonly:
            result|=0x0001
        if self.targetIsHidden:
            result|=0x0002
        if self.targetIsSysFile:
            result|=0x0004
        if self.targetIsVolume:
            result|=0x0008
        if self.targetIsDir:
            result|=0x0010
        if self.targetNeedsBackup:
            result|=0x0020
        if self.targetIsEncrypted:
            result|=0x0040
        if self.targetIsNormal:
            result|=0x0080
        if self.targetIsTempfile:
            result|=0x0100
        if self.targetIsSparse:
            result|=0x0200
        if self.targetHasReparse:
            result|=0x0400
        if self.targetIsCompressed:
            result|=0x0600
        if self.targetIsOffline:
            result|=0x0800
        return result

class _WindowsShortcutFlags:
    """
    The link flags of a shortcut (which optional data sections are present)
    """
    def __init__(self,flagsDword:typing.Optional[int]=None)->None:
        """
        :param flagsDword: flag bits to initialize from
        """
        self.hasShellItemId=False
        self.isFileOrDir=False
        self.hasDescription=False
        self.isRelative=False
        self.hasWorkingDirectory=False
        self.hasCommandLineArgs=False
        self.hasCustomIcon=False
        if flagsDword is not None:
            self.set(flagsDword)

    def set(self,flagsDword:int)->None:
        """
        Set the flags from a bit field

        :param flagsDword: flag bits
        """
        self.hasShellItemId=flagsDword&0x0001>0
        self.isFileOrDir=flagsDword&0x0002>0
        self.hasDescription=flagsDword&0x0004>0
        self.isRelative=flagsDword&0x0008>0
        self.hasWorkingDirectory=flagsDword&0x0010>0
        self.hasCommandLineArgs=flagsDword&0x0020>0
        self.hasCustomIcon=flagsDword&0x0040>0

    def __int__(self)->int:
        """
        The flags as a bit field
        """
        return self.get()
    def get(self)->int:
        """
        Get the flags as a bit field
        """
        result=0x0000
        if self.hasShellItemId:
            result|=0x0001
        if self.isFileOrDir:
            result|=0x0002
        if self.hasDescription:
            result|=0x0004
        if self.isRelative:
            result|=0x0008
        if self.hasWorkingDirectory:
            result|=0x0010
        if self.hasCommandLineArgs:
            result|=0x0020
        if self.hasCustomIcon:
            result|=0x0040
        return result

class _WindowsShortcutFileLocationInfo:
    """
    The file location info section of a shortcut
    """
    def __init__(self,fromStr:typing.Optional[bytes]=None)->None:
        """
        :param fromStr: raw section data to initialize from
        """
        self.LinkInfoSize=0
        self.LinkInfoHeaderSize=0
        self.LinkInfoFlags=0
        self.VolumeIDOffset=0
        self.LocalBasePathOffset=0
        self.CommonNetworkRelativeLinkOffset=0
        self.CommonPathSuffixOffset=0
        self.LocalBasePathOffsetUnicode=0
        self.CommonPathSuffixOffsetUnicode=0
        self.Data=None
        if fromStr is not None:
            self.set(fromStr)

    def set(self,fromStr:bytes)->None:
        """
        Parse the section from raw data

        :param fromStr: raw section data
        """
        DWORD=(4,'<I')
        names=[
            'LinkInfoSize',
            'LinkInfoHeaderSize',
            'LinkInfoFlags',
            'VolumeIDOffset',
            'LocalBasePathOffset',
            'CommonNetworkRelativeLinkOffset',
            'CommonPathSuffixOffset',
            'LocalBasePathOffsetUnicode',
            'CommonPathSuffixOffsetUnicode']
        offs=0
        for name in names:
            val=struct.unpack(DWORD[1],fromStr[offs:offs+DWORD[0]])[0]
            setattr(self,name,val)
            offs+=DWORD[0]
        self.Data=fromStr[offs:]

    def get(self)->bytes:
        """
        Get the section as raw data
        """
        DWORD=(4,'<I')
        names=[
            'LinkInfoSize',
            'LinkInfoHeaderSize',
            'LinkInfoFlags',
            'VolumeIDOffset',
            'LocalBasePathOffset',
            'CommonNetworkRelativeLinkOffset',
            'CommonPathSuffixOffset',
            'LocalBasePathOffsetUnicode',
            'CommonPathSuffixOffsetUnicode']
        data:typing.List[bytes]=[
            struct.pack(DWORD[1],getattr(self,name)) for name in names]
        if self.Data is not None:
            data.extend(self.Data)
        return b''.join(data)


class WindowsLnkFormat:
    """
    Manually reads/writes the windows lnk file format

    Therefore, unlike WindowsLink objects, this is os-independent!
    """
    START_BYTES=[0x4C,0x00,0x00,0x00]#[0x00,0x00,0x00,0x04]
    GUID_BYTES=[
        0x01,0x14,0x02,0x00,0x00,0x00,0x00,0x00,
        0xC0,0x00,0x00,0x00,0x00,0x00,0x00,0x46]
    # probably only SW_NORMAL, SW_SHOWMINIMIZED, SW_SHOWMAXIMIZED will work
    SW_HIDE=0
    SW_NORMAL=1
    SW_SHOWMINIMIZED=2
    SW_SHOWMAXIMIZED=3
    SW_SHOWNOACTIVATE=4
    SW_SHOW=5
    SW_MINIMIZE=6
    SW_SHOWMINNOACTIVE=7
    SW_SHOWNA=8
    SW_RESTORE=9
    SW_SHOWDEFAULT=10

    SW_strings=['SW_HIDE','SW_NORMAL','SW_SHOWMINIMIZED','SW_SHOWMAXIMIZED',
        'SW_SHOWNOACTIVATE','SW_SHOW','SW_MINIMIZE','SW_SHOWMINNOACTIVE',
        'SW_SHOWNA','SW_RESTORE','SW_SHOWDEFAULT']

    def __init__(self,linkFilename:typing.Optional[str]=None)->None:
        """
        :param linkFilename: the lnk file to load (if any)
        """
        self.flags=_WindowsShortcutFlags()
        self.fileAttr=_WindowsShortcutFileAttr()
        self.creationTime=0
        self.modificationTime=0
        self.accessTime=0
        self.fileLength=0
        self.iconNumber=0
        self.showWindowOptions=0
        self.hotKey=0
        self.description=None
        self.relativePath=None
        self.workingDirectory=None
        self.commandLine=None
        self.iconFile=None
        self.shellItemId=None
        self.linkFilename:typing.Optional[str]=None
        self.load(linkFilename)

    def __repr__(self)->str:
        """
        Get a string representation of this link
        """
        ret:typing.List[str]=[str(self.linkFilename)]
        if self.description is not None:
            ret.append('description='+self.description)
        if self.relativePath is not None:
            ret.append('relativePath='+self.relativePath)
        if self.workingDirectory is not None:
            ret.append('workingDirectory='+self.workingDirectory)
        if self.commandLine is not None:
            ret.append('commandLine='+self.commandLine)
        if self.iconFile is not None:
            ret.append('iconFile='+self.iconFile)
        return '\n\t'.join(ret)

    def load(self,linkFilename:typing.Optional[str])->None:
        """
        Load a link file

        :param linkFilename: the lnk file to load (".lnk" is added if needed)
        """
        if linkFilename is None:
            return
        if not os.path.exists(linkFilename) \
            and os.path.exists(linkFilename+'.lnk'):
            linkFilename=linkFilename+'.lnk'
        self.linkFilename=linkFilename
        if linkFilename.endswith('.lnk'):
            self._loadWinShortcut(linkFilename)

    def save(self,
        saveAsFilename:typing.Optional[str]=None,
        noClobberFile:bool=True,
        linkFilename:typing.Optional[str]=None
        )->None:
        """
        Save the link to a file

        :param saveAsFilename: where to save (default is the loaded file)
        :param noClobberFile: safeguard to never overwrite
            an actual file with a link
        """
        if saveAsFilename is None:
            if self.linkFilename is not None:
                saveAsFilename=self.linkFilename
            elif self.targetLocation is not None:
                saveAsFilename=self.targetLocation.rsplit(os.sep,1)[-1]
        if noClobberFile \
            and os.path.exists(saveAsFilename) \
            and WindowsLnkFormat.isLink(saveAsFilename)==False:
            #
            idx=1
            while True:
                fn:str='%s_%03d'%(saveAsFilename,idx)
                if not os.path.exists(fn) or WindowsLnkFormat.isLink(fn):
                    break
                idx+=1
            saveAsFilename=fn
        if self.linkType==LINKTYPE_SHORTCUT:
            self._saveWinShortcut(saveAsFilename)

    def _unpackString(self,f:typing.BinaryIO,str:bool=False)->str:
        """
        Read a null-terminated string from a file

        :param f: binary file to read from
        :param str: True to read 16-bit unicode characters, False to read bytes
        """
        strBytes:typing.List[str]=[]
        if str:
            while True:
                sz=f.read(2)
                if len(sz)<2:
                    break
                c=struct.unpack('<H',sz)[0]
                if c==0:
                    break
                strBytes.append(chr(c))
        else:
            while True:
                c=struct.unpack('B',f.read(1))[0]
                if c==0:
                    break
                strBytes.append(chr(c))
        return ''.join(strBytes)

    def _saveWinShortcut(self)->None:
        """
        Write the shortcut in lnk format (unfinished)
        """
        #BYTE=(1,'B')
        #WORD=(2,'<H')
        DWORD=(4,'<I')
        QWORD=(8,'<Q')
        vals:typing.List[typing.Tuple[str,typing.Tuple[int,str]]]=[
            ('flags',DWORD),
            ('fileAttr',DWORD),
            ('creationTime',QWORD),
            ('modificationTime',QWORD),
            ('accessTime',QWORD),
            ('fileLength',DWORD),
            ('iconNumber',DWORD),
            ('showWindowOptions',DWORD),
            ('hotKey',DWORD)
        ]
        f=open(linkFilename,'wb')
        # set the filetype info
        f.write(self.START_BYTES)
        f.write(self.GUID_BYTES)
        # header values
        for val in vals:
            f.write(struct.pack(val[1][1],int(self.getattr(val[0]))))
        # two reserved DWORDs
        f.write(struct.pack(DWORD[1][1],0))
        f.write(struct.pack(DWORD[1][1],0))
        # shell item id
        # if self.flags.hasShellItemId:
            # # read a ITEMIDLIST struct
            # size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            # if size>0:
                # self.shellItemId=f.read(size)
        # # File location info
        # size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
        # size=size-2 # subtract off the size of size
        # if size>0:
            # self.fileLocationInfo=f.read(size)
            # self.fileLocationInfo=_WindowsShortcutFileLocationInfo(self.fileLocationInfo)
        # # description
        # if self.flags.hasDescription:
            # size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            # self.description=f.read(size*2).decode('utf-16') # double the size, because, unicode # noqa: E501
        # # relative path
        # if self.flags.isRelative:
            # size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            # self.relativePath=f.read(size*2).decode('utf-16') # double the size, because, unicode # noqa: E501
        # # working directory
        # if self.flags.hasWorkingDirectory:
            # size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            # self.workingDirectory=f.read(size*2).decode('utf-16') # double the size, because, unicode # noqa: E501
        # # command line
        # if self.flags.hasCommandLineArgs:
            # size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            # self.commandLine=f.read(size*2).decode('utf-16') # double the size, because, unicode # noqa: E501
        # # icon file
        # if self.flags.hasCustomIcon:
            # size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            # self.iconFile=f.read(size*2).decode('utf-16') # double the size, because, unicode # noqa: E501
        # last is a QWORD length sometimes followed by extra crap if >0
        f.write(struct.pack(QWORD[1][1],0))

    def _loadWinShortcut(self,linkFilename:str)->None:
        """
        Read the shortcut from an lnk file

        :param linkFilename: the lnk file to read

        See also:
            http://fileanalysis.net/lnk/
        """
        #BYTE=(1,'B')
        WORD=(2,'<H')
        DWORD=(4,'<I')
        QWORD=(8,'<Q')
        vals:typing.List[typing.Tuple[str,typing.Tuple[int,str]]]=[
            ('flags',DWORD),
            ('fileAttr',DWORD),
            ('creationTime',QWORD),
            ('modificationTime',QWORD),
            ('accessTime',QWORD),
            ('fileLength',DWORD),
            ('iconNumber',DWORD),
            ('showWindowOptions',DWORD),
            ('hotKey',DWORD)
        ]
        f=open(linkFilename,'rb')
        # read the filetype info
        idguid=f.read(len(self.START_BYTES)+len(self.GUID_BYTES))
        #print(":".join("{:02x}".format(ord(c)) for c in idguid))
        if not WindowsLnkFormat.isLink(linkFilename,idguid):
            raise NotALinkException(linkFilename)
        # read the settings header
        for name,size in vals:
            q=struct.unpack(size[1],f.read(size[0]))[0]
            setattr(self,name,q)
        # expand what we have so far
        self.flags=_WindowsShortcutFlags(self.flags)
        self.fileAttr=_WindowsShortcutFileAttr(self.fileAttr)
        # two reserved DWORDs
        f.read(DWORD[0])
        f.read(DWORD[0])
        # read shell item id
        #   see:
        #   https://msdn.microsoft.com/en-us/library/windows/desktop/bb759800%28v=vs.85%29.aspx
        if self.flags.hasShellItemId:
            # read a ITEMIDLIST struct
            size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            if size>0:
                self.shellItemId=f.read(size)
        # File location info
        size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
        size=size-2 # subtract off the size of size
        if size>0:
            self.fileLocationInfo=f.read(size)
            self.fileLocationInfo=_WindowsShortcutFileLocationInfo(
                self.fileLocationInfo)
        # description
        if self.flags.hasDescription:
            size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            self.description=f.read(size*2).decode('utf-16') # double the size, because, unicode # noqa: E501
        # relative path
        if self.flags.isRelative:
            size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            self.relativePath=f.read(size*2).decode('utf-16') # double the size, because, unicode # noqa: E501
        # working directory
        if self.flags.hasWorkingDirectory:
            size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            self.workingDirectory=f.read(size*2).decode('utf-16') # double the size, because, unicode # noqa: E501
        # command line
        if self.flags.hasCommandLineArgs:
            size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            self.commandLine=f.read(size*2).decode('utf-16') # double the size, because, unicode # noqa: E501
        # icon file
        if self.flags.hasCustomIcon:
            size=struct.unpack(WORD[1],f.read(WORD[0]))[0]
            self.iconFile=f.read(size*2).decode('utf-16') # double the size, because, unicode # noqa: E501
        # last is a QWORD length sometimes followed by extra crap if >0


    # if linktype is impossible (for instance, hardlink across partitions)
    # the linktype will degrade down to what is acceptable
    #
    # Relative specifies relative or absolute linkage
    #
    # Create path will create any path steps in targetLocation that do not yet exist # noqa: E501
    #
    # NOTE: creating some types of links may require admin privelages
    #
    # See Also:
    #    http://www.flexhex.com/docs/articles/hard-links.phtml
    #    alternatively, use mklink from the command line
    def _createLink(self,
        targetLocation:str,
        linkLocation:typing.Optional[str]=None,
        linkType:int=LINKTYPE_SYMBOLIC_LINK,
        relative:bool=False,
        createPath:bool=True
        )->None:
        """
        Create a link to targetLocation (see notes above)

        :param targetLocation: what the link points to
        :param linkLocation: where to create the link
            (default is the target's name in the current directory)
        :param linkType: the type of link to create
        :param relative: relative or absolute linkage
        :param createPath: create any missing path steps in targetLocation
        """
        import ctypes
        if linkLocation is None:
            parts=targetLocation.rsplit(os.sep,1)
            if len(parts)==1:
                linkLocation='Link to '+parts[0]
            else:
                linkLocation=parts[1]
        linkLocation=os.path.abspath(linkLocation) # since this can always be absolute # noqa: E501
        # downgrade link type if necessary
        if linkType==LINKTYPE_HARD:
            if os.path.isdir(targetLocation):
                print("Cannot hard-link to directory.  Downgrading.")
                linkType=LINKTYPE_JUNCTION
            else:
                # don't know if I need to do this
                targetLocation=os.path.abspath(targetLocation)
        if linkType==LINKTYPE_JUNCTION:
            print("LINKTYPE_JUNCTION not implemented.  Downgrading.")
            linkType=LINKTYPE_SYMBOLIC
        # go for it
        print('Link "'+linkLocation+'" => "'+targetLocation+'"')
        linkLocationPtr=ctypes.c_wchar_p(str(linkLocation))
        targetLocationPtr=ctypes.c_wchar_p(str(targetLocation))
        if linkType==LINKTYPE_SHORTCUT:
            pass
        elif linkType==LINKTYPE_SYMBOLIC:
            result=ctypes.windll.kernel32.CreateSymbolicLinkW(
                targetLocationPtr,
                linkLocationPtr,
                int(os.path.isdir(linkLocation)))
            if result==0:
                code=ctypes.GetLastError()
                print('ERR('+str(code)+'): '+ctypes.FormatError(code))
            else:
                print('SUCCESS')
        elif linkType==LINKTYPE_JUNCTION:
            pass
        elif linkType==LINKTYPE_HARD:
            result=ctypes.windll.kernel32.CreateHardLinkW(
                targetLocationPtr,
                linkLocationPtr,
                None) # third param is always NULL
            if result==0:
                code=ctypes.GetLastError()
                print('ERR('+str(code)+'): '+ctypes.FormatError(code))
            else:
                print('SUCCESS')

    def getHotKey(self)->int:
        """
        TODO: should probably use __getattr__ or decorator for this stuff
        """
        return self.hotKey

    @property
    def comment(self)->typing.Optional[str]:
        """
        The link's description
        """
        return self.description
    @comment.setter
    def comment(self,comment:typing.Optional[str])->None:
        """
        :param comment: the new description
        """
        self.description=comment

    @property
    def path(self)->str:
        """
        Absolute path of the link's relative path
        """
        relativePath=self.relativePath
        if relativePath is None:
            relativePath=os.getcwd()
        return os.path.abspath(relativePath)
    def getTarget(self)->str:
        """
        Get the link target
        """
        return self.path
    def getPath(self)->str:
        """
        Get the link path
        """
        return self.path

    def isFile(self)->bool:
        """
        Is the target a file?
        """
        return os.path.isfile(self.getPath())

    def isDir(self)->bool:
        """
        Is the target a directory?
        """
        return os.path.isdir(self.getPath())

    def exists(self)->bool:
        """
        Does the target exist?
        """
        return os.path.exists(self.getPath())

    @staticmethod
    def isLink(
        filename:typing.Optional[str],
        fileBuffer:typing.Optional[bytes]=None
        )->bool:
        """
        determine if the given file is a link or shortcut

        if filename is None, base the determination soley on the data buffer

        if fileBuffer is None, will open the filename ourselves

        :param filename: file to check
        :param fileBuffer: the first bytes of the file
        """
        return WindowsLnkFormat.isShortcut(filename,fileBuffer)

    @staticmethod
    def isShortcut(
        filename:typing.Optional[str],
        fileBuffer:typing.Optional[bytes]=None
        )->bool:
        """
        determine if the given file is a windows shortcut

        if filename is None, base the determination soley on the data buffer

        if fileBuffer is None, will open the filename ourselves

        :param filename: file to check
        :param fileBuffer: the first bytes of the file
        """
        if filename is None or filename.rsplit('.',1)[-1].lower()=='lnk':
            if fileBuffer is None:
                found=False
                with open(filename,'rb') as f:
                    found=True
                    fileBuffer=f.read(
                        len(WindowsLnkFormat.START_BYTES)
                        +len(WindowsLnkFormat.GUID_BYTES))
                if not found:
                    return False
            i=0
            for b in WindowsLnkFormat.START_BYTES:
                #print('0x%02X == 0x%02X'%(ord(fileBuffer[i]),b))
                if fileBuffer[i]!=b:
                    return False
                i=i+1
            for b in WindowsLnkFormat.GUID_BYTES:
                #print('0x%02X == 0x%02X'%(ord(fileBuffer[i]),b))
                if fileBuffer[i]!=b:
                    return False
                i=i+1
            return True
        return False


def _getWindowsLinkTarget( # type: ignore
    link:str)->str:
    """
    this is old.

    dereference a windows shortcut to an actual file name

    EXPERIMENTAL.  See also:
    http://code.google.com/p/8bits/downloads/detail?name=The_Windows_Shortcut_File_Format.pdf

    :param link: path to the shortcut
    """
    import struct
    data=''
    with open(link,'rb') as f:
        f.seek(0x4e)
        while True:
            itemLength=struct.unpack('>H',f.read(2))[0]
            if itemLength==0:
                break
            item=struct.unpack(str(itemLength-2)+'b',f.read(itemLength-2))
            start=12
            for n in range(start,len(item)):
                if item[n]==0:
                    filename=struct.unpack(str(n-start-1)+'s',item[start:n])
                    print(filename)
                    break
        data=str(data)
        print('Read link:',data)
    return data


def showAllShortcuts(path:str,recursive:bool=True)->None:
    """
    Find and display all links

    same as showAllLinks()

    :param path: where to start searching
    :param recursive: True/False whether to search sub-directories
    """
    return showAllLinks(path,recursive)
def showAllLinks(path:str,recursive:bool=True)->None:
    """
    Find and display all links

    :param path: where to start searching
    :param recursive: True/False whether to search sub-directories
    """
    from .findReplace import findAll
    linkFinderGenerator=findAll(
        path,yeild_files=False,yeild_shortcuts=True,recursive=recursive)
    for sc in linkFinderGenerator:
        sc=winshell.shortcut(sc)
        print(sc.lnk_filepath+' => '+sc.path)


def createShortcut(
    inDir:str,
    target:str,
    name:typing.Optional[str]=None,
    description:typing.Optional[str]=None,
    icon:typing.Optional[str]=None,
    hotkey:typing.Optional[str]=None
    )->None:
    """
    Will not work with URL links

    Same thing as createLink

    :param inDir: directory to create the shortcut in
    :param target: what the shortcut points to
    :param name: name of the shortcut (default is the target's name)
    :param description: shortcut description
    :param icon: icon location
    :param hotkey: shortcut hotkey
    """
    return createLink(inDir,target,name,description,icon,hotkey)
def createLink(
    inDir:str,
    target:str,
    name:typing.Optional[str]=None,
    description:typing.Optional[str]=None,
    icon:typing.Optional[str]=None,
    hotkey:typing.Optional[str]=None
    )->None:
    """
    Will not work with URL links

    :param inDir: directory to create the shortcut in
    :param target: what the shortcut points to
    :param name: name of the shortcut (default is the target's name)
    :param description: shortcut description
    :param icon: icon location
    :param hotkey: shortcut hotkey
    """
    import winshell
    if name is None:
        name=target.rsplit(os.sep,1)[-1]
    if name.rsplit('.',1)[-1]!='lnk':
        name=name+'.lnk'
    s=winshell.shortcut().from_target(target)
    #s.working_directory="" # this is the working directory for the link, use like if it's a shortcut to an excutable # noqa: E501
    s.lnk_filepath=inDir+os.sep+name
    if icon is not None:
        s.icon_location=icon
    if description is not None:
        s.description=description
    if hotkey is not None:
        s.hotkey=hotkey
    print(s)
    print(dir(s))
    s.write()


def finalPath(path:str,absolute:bool=False)->str:
    """
    Returns either the path given, or if it's a link, the path it points to

    * Will follow link-to-a-links

    Could raise RecursiveLinkException

    :param path: the path to resolve
    :param absolute: True/False return the absolute path of the
        given path instead of following it
    """
    followed:typing.List[str]=[]
    while True:
        abspath=os.path.abspath(path)
        if abspath in followed:
            followed.append(abspath)
            raise RecursiveLinkException(followed)
        followed.append(abspath)
        if path.endswith('.lnk'):
            l=WindowsLnkFormat(path)
            path=(l.getTarget())
        elif not os.path.exists(path) and os.path.exists(path+'.lnk'):
            l=WindowsLnkFormat(path)
            path=(l.getTarget())
        else:
            break
    if absolute:
        return abspath
    return path


def cmdline(args:typing.Iterable[str])->int:
    """
    Run the command line

    :param args: command line arguments (WITHOUT the filename)
    """
    lnk=WindowsLnkFormat(
        os.path.abspath(__file__).rsplit(os.sep,1)[0]\
        +os.sep+'test'+os.sep+'target_shortcut.lnk')
    print(str(lnk))
    return 0


if __name__=='__main__':
    import sys
    sys.exit(cmdline(sys.argv[1:]))

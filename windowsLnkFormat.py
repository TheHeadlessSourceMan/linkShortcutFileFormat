#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Manually reads/writes the windows lnk file format

Therefore, unlike symlinks, this is os-independent and
uses no windows libraries!

See:
    [MS-SHLLINK] Shell Link (.LNK) Binary File Format
"""
import typing
import struct
import os
import re
import time
import uuid
from paths import UrlCompatible,FilePath,asFilePath,asFileString
from paths.relativePathCleanup import cleanup
from .linkExceptions import NotALinkException,LinkException


_ANSI='mbcs' if os.name=='nt' else 'cp1252'
_WINDOWS_PATH=re.compile(r'^([A-Za-z]:[\\/]|\\\\)')
_ENVIRONMENT_VARIABLE=re.compile(r'%([^%]+)%')

# LinkFlags
_HAS_ID_LIST=0x00000001
_HAS_LINK_INFO=0x00000002
_HAS_NAME=0x00000004
_HAS_RELATIVE_PATH=0x00000008
_HAS_WORKING_DIR=0x00000010
_HAS_ARGUMENTS=0x00000020
_HAS_ICON_LOCATION=0x00000040
_IS_UNICODE=0x00000080
_FORCE_NO_LINK_INFO=0x00000100
_HAS_EXP_STRING=0x00000200
_HAS_DARWIN_ID=0x00001000
_HAS_EXP_ICON=0x00004000
_RUN_WITH_SHIM_LAYER=0x00020000
_MANAGED_FLAGS=0x000000FF

# ExtraData block signatures
CONSOLE_PROPS_SIG=0xA0000002
CONSOLE_FE_PROPS_SIG=0xA0000004
DARWIN_PROPS_SIG=0xA0000006
ENVIRONMENT_PROPS_SIG=0xA0000001
ICON_ENVIRONMENT_PROPS_SIG=0xA0000007
KNOWN_FOLDER_PROPS_SIG=0xA000000B
PROPERTY_STORE_PROPS_SIG=0xA0000009
SHIM_PROPS_SIG=0xA0000008
SPECIAL_FOLDER_PROPS_SIG=0xA0000005
TRACKER_PROPS_SIG=0xA0000003
VISTA_AND_ABOVE_IDLIST_PROPS_SIG=0xA000000C

# block signature -> (HasXxx link flag that must mirror its presence)
_BLOCK_FLAGS={
    ENVIRONMENT_PROPS_SIG:_HAS_EXP_STRING,
    DARWIN_PROPS_SIG:_HAS_DARWIN_ID,
    ICON_ENVIRONMENT_PROPS_SIG:_HAS_EXP_ICON,
    SHIM_PROPS_SIG:_RUN_WITH_SHIM_LAYER,
    }

# hotkey modifier bits (high byte of the hotkey)
HOTKEYF_SHIFT=0x01
HOTKEYF_CONTROL=0x02
HOTKEYF_ALT=0x04

# LinkInfo drive types
DRIVE_UNKNOWN=0
DRIVE_NO_ROOT_DIR=1
DRIVE_REMOVABLE=2
DRIVE_FIXED=3
DRIVE_REMOTE=4
DRIVE_CDROM=5
DRIVE_RAMDISK=6

# FileAttributes
FILE_ATTRIBUTE_READONLY=0x0001
FILE_ATTRIBUTE_HIDDEN=0x0002
FILE_ATTRIBUTE_SYSTEM=0x0004
FILE_ATTRIBUTE_DIRECTORY=0x0010
FILE_ATTRIBUTE_ARCHIVE=0x0020
FILE_ATTRIBUTE_ENCRYPTED=0x0040
FILE_ATTRIBUTE_NORMAL=0x0080
FILE_ATTRIBUTE_TEMPORARY=0x0100
FILE_ATTRIBUTE_SPARSE_FILE=0x0200
FILE_ATTRIBUTE_REPARSE_POINT=0x0400
FILE_ATTRIBUTE_COMPRESSED=0x0800
FILE_ATTRIBUTE_OFFLINE=0x1000
FILE_ATTRIBUTE_NOT_CONTENT_INDEXED=0x2000


class _WindowsShortcutFileAttr:
    """
    The file attribute flags of a shortcut's target
    """
    def __init__(self,attrDword:int=0)->None:
        """
        :param attrDword: attribute bits to initialize from
        """
        self.value=attrDword

    def _bit(self,mask:int)->bool:
        return self.value&mask>0
    def _setBit(self,mask:int,on:bool)->None:
        if on:
            self.value|=mask
        else:
            self.value&=~mask

    @property
    def targetIsReadonly(self)->bool:
        """ target is read-only """
        return self._bit(FILE_ATTRIBUTE_READONLY)
    @property
    def targetIsHidden(self)->bool:
        """ target is hidden """
        return self._bit(FILE_ATTRIBUTE_HIDDEN)
    @property
    def targetIsSysFile(self)->bool:
        """ target is a system file """
        return self._bit(FILE_ATTRIBUTE_SYSTEM)
    @property
    def targetIsDir(self)->bool:
        """ target is a directory """
        return self._bit(FILE_ATTRIBUTE_DIRECTORY)
    @targetIsDir.setter
    def targetIsDir(self,isDir:bool)->None:
        self._setBit(FILE_ATTRIBUTE_DIRECTORY,isDir)
    @property
    def targetHasReparse(self)->bool:
        """ target is a reparse point (symlink/junction) """
        return self._bit(FILE_ATTRIBUTE_REPARSE_POINT)
    @property
    def targetIsArchive(self)->bool:
        """ target is marked for archiving """
        return self._bit(FILE_ATTRIBUTE_ARCHIVE)
    @property
    def targetIsEncrypted(self)->bool:
        """ target is encrypted """
        return self._bit(FILE_ATTRIBUTE_ENCRYPTED)
    @property
    def targetIsNormal(self)->bool:
        """ target has no other attributes set """
        return self._bit(FILE_ATTRIBUTE_NORMAL)
    @property
    def targetIsTemporary(self)->bool:
        """ target is temporary """
        return self._bit(FILE_ATTRIBUTE_TEMPORARY)
    @property
    def targetIsSparse(self)->bool:
        """ target is a sparse file """
        return self._bit(FILE_ATTRIBUTE_SPARSE_FILE)
    @property
    def targetIsCompressed(self)->bool:
        """ target is compressed """
        return self._bit(FILE_ATTRIBUTE_COMPRESSED)
    @property
    def targetIsOffline(self)->bool:
        """ target data is not immediately available """
        return self._bit(FILE_ATTRIBUTE_OFFLINE)
    @property
    def targetIsNotIndexed(self)->bool:
        """ target is excluded from content indexing """
        return self._bit(FILE_ATTRIBUTE_NOT_CONTENT_INDEXED)

    def __int__(self)->int:
        """
        The attributes as a bit field
        """
        return self.value


class _WindowsShortcutFlags:
    """
    The link flags of a shortcut (which optional data sections are present)
    """
    def __init__(self,flagsDword:int=0)->None:
        """
        :param flagsDword: flag bits to initialize from
        """
        self.value=flagsDword

    def _bit(self,mask:int)->bool:
        return self.value&mask>0

    @property
    def hasShellItemId(self)->bool:
        """ has a LinkTargetIDList """
        return self._bit(_HAS_ID_LIST)
    @property
    def hasLinkInfo(self)->bool:
        """ has a LinkInfo section """
        return self._bit(_HAS_LINK_INFO)
    @property
    def hasDescription(self)->bool:
        """ has a description string """
        return self._bit(_HAS_NAME)
    @property
    def isRelative(self)->bool:
        """ has a relative path string """
        return self._bit(_HAS_RELATIVE_PATH)
    @property
    def hasWorkingDirectory(self)->bool:
        """ has a working directory string """
        return self._bit(_HAS_WORKING_DIR)
    @property
    def hasCommandLineArgs(self)->bool:
        """ has a command line arguments string """
        return self._bit(_HAS_ARGUMENTS)
    @property
    def hasCustomIcon(self)->bool:
        """ has an icon location string """
        return self._bit(_HAS_ICON_LOCATION)
    @property
    def isUnicode(self)->bool:
        """ string data is utf-16 (otherwise it is ansi) """
        return self._bit(_IS_UNICODE)
    @property
    def forceNoLinkInfo(self)->bool:
        """ LinkInfo is ignored even if present """
        return self._bit(_FORCE_NO_LINK_INFO)
    @property
    def hasEnvironmentTarget(self)->bool:
        """ has an EnvironmentVariableDataBlock """
        return self._bit(_HAS_EXP_STRING)
    @property
    def runInSeparateProcess(self)->bool:
        """ 16-bit target runs in a separate VDM """
        return self._bit(0x00000400)
    @property
    def hasDarwinId(self)->bool:
        """ has a DarwinDataBlock """
        return self._bit(_HAS_DARWIN_ID)
    @property
    def runAsUser(self)->bool:
        """ target runs as a different user """
        return self._bit(0x00002000)
    @property
    def hasExpIcon(self)->bool:
        """ has an IconEnvironmentDataBlock """
        return self._bit(_HAS_EXP_ICON)
    @property
    def noPidlAlias(self)->bool:
        """ IDList is not aliased to a known folder """
        return self._bit(0x00008000)
    @property
    def runWithShimLayer(self)->bool:
        """ has a ShimDataBlock """
        return self._bit(_RUN_WITH_SHIM_LAYER)
    @property
    def forceNoLinkTrack(self)->bool:
        """ TrackerDataBlock is ignored """
        return self._bit(0x00040000)
    @property
    def enableTargetMetadata(self)->bool:
        """ target properties are collected into the PropertyStore """
        return self._bit(0x00080000)
    @property
    def disableLinkPathTracking(self)->bool:
        """ EnvironmentVariableDataBlock is ignored """
        return self._bit(0x00100000)
    @property
    def disableKnownFolderTracking(self)->bool:
        """ SpecialFolder/KnownFolder blocks are ignored """
        return self._bit(0x00200000)
    @property
    def disableKnownFolderAlias(self)->bool:
        """ known folder alias is not used when saving the IDList """
        return self._bit(0x00400000)
    @property
    def allowLinkToLink(self)->bool:
        """ link may point at another link """
        return self._bit(0x00800000)
    @property
    def unaliasOnSave(self)->bool:
        """ IDList is unaliased when saved """
        return self._bit(0x01000000)
    @property
    def preferEnvironmentPath(self)->bool:
        """ environment path is preferred over the IDList """
        return self._bit(0x02000000)
    @property
    def keepLocalIdListForUncTarget(self)->bool:
        """ local IDList is kept for UNC targets """
        return self._bit(0x04000000)

    def __int__(self)->int:
        """
        The flags as a bit field
        """
        return self.value


def _cstr(buf:bytes,offset:int,unicode:bool=False)->str:
    """
    Read a null-terminated string from a buffer

    :param buf: the buffer
    :param offset: where the string starts
    :param unicode: utf-16 (otherwise ansi)
    """
    if unicode:
        end=offset
        while end+1<len(buf) and buf[end:end+2]!=b'\x00\x00':
            end+=2
        return buf[offset:end].decode('utf-16-le','replace')
    end=buf.find(b'\x00',offset)
    if end<0:
        end=len(buf)
    return buf[offset:end].decode(_ANSI,'replace')


def _ansiz(s:str)->bytes:
    """ null-terminated ansi string """
    return s.encode(_ANSI,'replace')+b'\x00'


def _unicodez(s:str)->bytes:
    """ null-terminated utf-16 string """
    return s.encode('utf-16-le')+b'\x00\x00'


def _expandWindowsEnvironment(text:str)->str:
    """Expand Windows-style percent variables without changing unknown ones."""
    environment={key.casefold():value for key,value in os.environ.items()}
    return _ENVIRONMENT_VARIABLE.sub(
        lambda match:environment.get(match.group(1).casefold(),match.group(0)),
        text)


class ConsoleData(typing.NamedTuple):
    """ ConsoleDataBlock contents (console window properties) """
    fillAttributes:int=7
    popupFillAttributes:int=0xF5
    screenBufferSize:typing.Tuple[int,int]=(80,300)
    windowSize:typing.Tuple[int,int]=(80,25)
    windowOrigin:typing.Tuple[int,int]=(0,0)
    fontSize:int=0
    fontFamily:int=0
    fontWeight:int=0
    faceName:str=''
    cursorSize:int=25
    fullScreen:int=0
    quickEdit:int=0
    insertMode:int=1
    autoPosition:int=1
    historyBufferSize:int=50
    numberOfHistoryBuffers:int=4
    historyNoDup:int=0
    colorTable:typing.Tuple[int,...]=(0,)*16


class TrackerData(typing.NamedTuple):
    """ TrackerDataBlock contents (distributed link tracking) """
    machineId:str
    volumeDroid:uuid.UUID
    fileDroid:uuid.UUID
    volumeDroidBirth:uuid.UUID
    fileDroidBirth:uuid.UUID


_CONSOLE_FMT='<HHhhhhhhIIIII64s8I16I'
_NAME_BLOCK_SIZE=0x314


def _packConsole(c:ConsoleData)->bytes:
    """ ConsoleDataBlock body """
    return struct.pack(_CONSOLE_FMT,
        c.fillAttributes,c.popupFillAttributes,
        *c.screenBufferSize,*c.windowSize,*c.windowOrigin,
        0,0,c.fontSize,c.fontFamily,c.fontWeight,
        c.faceName.encode('utf-16-le')[:62],
        c.cursorSize,c.fullScreen,c.quickEdit,c.insertMode,c.autoPosition,
        c.historyBufferSize,c.numberOfHistoryBuffers,c.historyNoDup,
        *c.colorTable)


def _unpackConsole(body:bytes)->ConsoleData:
    """ parse a ConsoleDataBlock body """
    v=struct.unpack(_CONSOLE_FMT,body[:struct.calcsize(_CONSOLE_FMT)])
    return ConsoleData(
        v[0],v[1],(v[2],v[3]),(v[4],v[5]),(v[6],v[7]),
        v[10],v[11],v[12],
        v[13].decode('utf-16-le','replace').split('\x00',1)[0],
        *v[14:22],tuple(v[22:38]))


def _packNameBlock(text:str)->bytes:
    """ body of the blocks holding an ansi (260) and a unicode (260) path """
    ansi=text.encode(_ANSI,'replace')[:259]
    wide=text.encode('utf-16-le')[:518]
    return ansi.ljust(260,b'\x00')+wide.ljust(520,b'\x00')


def _unpackNameBlock(body:bytes)->str:
    """ read the path from an ansi+unicode block body (prefers unicode) """
    wide=_cstr(body,260,True) if len(body)>=262 else ''
    return wide or _cstr(body[:260],0)


def _filetimeNow()->int:
    """ the current time as a windows FILETIME """
    return int(time.time()*10000000)+116444736000000000


def _joinPath(base:typing.Optional[str],suffix:typing.Optional[str])->str:
    """
    Join the base and suffix paths found in a LinkInfo section

    :param base: base path
    :param suffix: common path suffix
    """
    if not base:
        return suffix or ''
    if not suffix:
        return base
    if base.endswith('\\'):
        return base+suffix
    return base+'\\'+suffix


class WindowsLnkFormat:
    """
    Manually reads/writes the windows lnk file format

    Therefore, unlike WindowsLink objects, this is os-independent!
    """
    HEADER_SIZE=0x4C
    START_BYTES=[0x4C,0x00,0x00,0x00]
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

    def __init__(self,linkFilename:typing.Optional[UrlCompatible]=None)->None:
        """
        :param linkFilename: the lnk file to load (if any)
        """
        self.flags=_WindowsShortcutFlags()
        self.fileAttr=_WindowsShortcutFileAttr()
        self.creationTime=0
        self.accessTime=0
        self.modificationTime=0
        self.fileLength=0
        self.iconNumber=0
        self.showWindowOptions=WindowsLnkFormat.SW_NORMAL
        self.hotKey=0
        self.description:typing.Optional[str]=None
        self.relativePath:typing.Optional[str]=None
        self.workingDirectory:typing.Optional[str]=None
        self.commandLine:typing.Optional[str]=None
        self.iconFile:typing.Optional[str]=None
        self.shellItemId:typing.Optional[bytes]=None
        # ExtraData blocks as (signature,body) in file order
        self.extraBlocks:typing.List[typing.Tuple[int,bytes]]=[]
        # LinkInfo contents
        self.targetPath:typing.Optional[str]=None
        self.uncPath:typing.Optional[str]=None
        self.driveType=0
        self.driveSerialNumber=0
        self.volumeLabel=''
        self.networkProviderType=0
        self.networkDeviceName:typing.Optional[str]=None
        self.linkFilename:typing.Optional[FilePath]=None
        if linkFilename is not None:
            self.load(linkFilename)

    def __repr__(self)->str:
        """
        Get a string representation of this link
        """
        ret:typing.List[str]=[str(self.linkFilename)]
        if self.targetPath is not None:
            ret.append('targetPath='+self.targetPath)
        if self.uncPath is not None:
            ret.append('uncPath='+self.uncPath)
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

    # ---- loading ----

    def load(self,linkFilename:UrlCompatible)->None:
        """
        Load a link file

        :param linkFilename: the lnk file to load (".lnk" is added if needed)
        """
        path=asFilePath(linkFilename)
        if not path.exists():
            withExtension=FilePath(str(path)+'.lnk')
            if withExtension.exists():
                path=withExtension
        data=path.pathlibPath.read_bytes()
        self.linkFilename=path
        self.parse(data)

    def parse(self,data:bytes)->None:
        """
        Parse the contents of an lnk file

        :param data: the entire file contents
        """
        name=str(self.linkFilename)
        if len(data)<WindowsLnkFormat.HEADER_SIZE \
            or not WindowsLnkFormat.isLink(None,data[:20]):
            raise NotALinkException(name)
        self.targetPath=None
        self.uncPath=None
        self.networkProviderType=0
        self.networkDeviceName=None
        try:
            (flags,attrs,ctime,atime,mtime,fsize,iconIdx,show,hotkey
                )=struct.unpack_from('<IIQQQIiIH',data,20)
            self.flags=_WindowsShortcutFlags(flags)
            self.fileAttr=_WindowsShortcutFileAttr(attrs)
            self.creationTime=ctime
            self.accessTime=atime
            self.modificationTime=mtime
            self.fileLength=fsize
            self.iconNumber=iconIdx
            self.showWindowOptions=show
            self.hotKey=hotkey
            offs=WindowsLnkFormat.HEADER_SIZE
            self.shellItemId=None
            if self.flags.hasShellItemId:
                size=struct.unpack_from('<H',data,offs)[0]
                self.shellItemId=data[offs+2:offs+2+size]
                offs+=2+size
            if self.flags.hasLinkInfo:
                size=struct.unpack_from('<I',data,offs)[0]
                if not self.flags.forceNoLinkInfo:
                    self._parseLinkInfo(data[offs:offs+size])
                offs+=size
            if self.targetPath is None and self.shellItemId:
                self.targetPath=self._pathFromIdList(self.shellItemId)
            unicode=self.flags.isUnicode
            strings:typing.List[typing.Optional[str]]=[]
            for present in (
                self.flags.hasDescription,
                self.flags.isRelative,
                self.flags.hasWorkingDirectory,
                self.flags.hasCommandLineArgs,
                self.flags.hasCustomIcon):
                s=None
                if present:
                    count=struct.unpack_from('<H',data,offs)[0]
                    offs+=2
                    if unicode:
                        s=data[offs:offs+count*2].decode('utf-16-le','replace')
                        offs+=count*2
                    else:
                        s=data[offs:offs+count].decode(_ANSI,'replace')
                        offs+=count
                strings.append(s)
            (self.description,self.relativePath,self.workingDirectory,
                self.commandLine,self.iconFile)=strings
            self.extraBlocks=self._parseExtraData(data[offs:])
        except struct.error as e:
            raise NotALinkException(name+' (truncated: '+str(e)+')')

    def _parseLinkInfo(self,buf:bytes)->None:
        """
        Parse a LinkInfo section

        :param buf: the entire LinkInfo section
        """
        (_,headerSize,infoFlags,volumeOffset,localOffset,
            networkOffset,suffixOffset)=struct.unpack_from('<7I',buf,0)
        localUnicode=0
        suffixUnicode=0
        if headerSize>=0x24:
            localUnicode,suffixUnicode=struct.unpack_from('<2I',buf,28)
        suffix=''
        if suffixUnicode:
            suffix=_cstr(buf,suffixUnicode,True)
        elif suffixOffset:
            suffix=_cstr(buf,suffixOffset)
        if infoFlags&0x1:
            base=''
            if localUnicode:
                base=_cstr(buf,localUnicode,True)
            elif localOffset:
                base=_cstr(buf,localOffset)
            self.targetPath=_joinPath(base,suffix)
            if volumeOffset:
                (_,self.driveType,self.driveSerialNumber,labelOffset
                    )=struct.unpack_from('<4I',buf,volumeOffset)
                if labelOffset==0x14:
                    labelUnicode=struct.unpack_from(
                        '<I',buf,volumeOffset+16)[0]
                    self.volumeLabel=_cstr(
                        buf,volumeOffset+labelUnicode,True)
                else:
                    self.volumeLabel=_cstr(buf,volumeOffset+labelOffset)
        if infoFlags&0x2 and networkOffset:
            (_,netFlags,netNameOffset,deviceOffset,providerType
                )=struct.unpack_from('<5I',buf,networkOffset)
            if netFlags&0x2: # ValidNetType
                self.networkProviderType=providerType
            if netNameOffset>0x14:
                netNameUnicode,deviceUnicode=struct.unpack_from(
                    '<2I',buf,networkOffset+20)
                netName=_cstr(buf,networkOffset+netNameUnicode,True)
                if netFlags&0x1 and deviceUnicode:
                    self.networkDeviceName=_cstr(
                        buf,networkOffset+deviceUnicode,True)
            else:
                netName=_cstr(buf,networkOffset+netNameOffset)
            if netFlags&0x1 and deviceOffset \
                and self.networkDeviceName is None: # ValidDevice
                self.networkDeviceName=_cstr(
                    buf,networkOffset+deviceOffset)
            self.uncPath=_joinPath(netName,suffix)
            if self.targetPath is None:
                self.targetPath=self.uncPath

    @staticmethod
    def _parseExtraData(
        buf:bytes
        )->typing.List[typing.Tuple[int,bytes]]:
        """
        Split the ExtraData section into blocks (up to the terminal block)

        :param buf: everything after the string data
        """
        blocks:typing.List[typing.Tuple[int,bytes]]=[]
        offs=0
        while offs+8<=len(buf):
            size,sig=struct.unpack_from('<II',buf,offs)
            if size==0:
                break
            if size<8 or size>len(buf)-offs:
                raise struct.error('invalid ExtraData block size')
            blocks.append((sig,buf[offs+8:offs+size]))
            offs+=size
        return blocks

    @property
    def extraData(self)->bytes:
        """
        The serialized ExtraData section (including the terminal block)
        """
        out=[struct.pack('<II',len(b)+8,sig)+b for sig,b in self.extraBlocks]
        out.append(b'\x00\x00\x00\x00')
        return b''.join(out)

    def getExtraBlock(self,signature:int)->typing.Optional[bytes]:
        """
        The body of the first ExtraData block with the given signature

        :param signature: the block signature (see the *_SIG constants)
        """
        for sig,body in self.extraBlocks:
            if sig==signature:
                return body
        return None

    def setExtraBlock(self,signature:int,body:typing.Optional[bytes])->None:
        """
        Add, replace or (with None) remove an ExtraData block

        :param signature: the block signature (see the *_SIG constants)
        :param body: the block contents (after size and signature)
        """
        others=[(s,b) for s,b in self.extraBlocks if s!=signature]
        if body is None:
            self.extraBlocks=others
            return
        for i,(s,_) in enumerate(self.extraBlocks):
            if s==signature:
                self.extraBlocks[i]=(signature,body)
                return
        self.extraBlocks.append((signature,body))

    def _nameBlock(self,signature:int)->typing.Optional[str]:
        body=self.getExtraBlock(signature)
        return None if body is None else _unpackNameBlock(body)

    def _setNameBlock(self,signature:int,text:typing.Optional[str])->None:
        self.setExtraBlock(
            signature,None if text is None else _packNameBlock(text))

    @property
    def environmentTarget(self)->typing.Optional[str]:
        """
        target path with environment variables (eg %windir%\\x.exe)
        """
        return self._nameBlock(ENVIRONMENT_PROPS_SIG)
    @environmentTarget.setter
    def environmentTarget(self,text:typing.Optional[str])->None:
        self._setNameBlock(ENVIRONMENT_PROPS_SIG,text)

    @property
    def iconEnvironmentPath(self)->typing.Optional[str]:
        """
        icon path with environment variables
        """
        return self._nameBlock(ICON_ENVIRONMENT_PROPS_SIG)
    @iconEnvironmentPath.setter
    def iconEnvironmentPath(self,text:typing.Optional[str])->None:
        self._setNameBlock(ICON_ENVIRONMENT_PROPS_SIG,text)

    @property
    def darwinId(self)->typing.Optional[str]:
        """
        application identifier (Windows Installer advertised shortcut)
        """
        return self._nameBlock(DARWIN_PROPS_SIG)
    @darwinId.setter
    def darwinId(self,text:typing.Optional[str])->None:
        self._setNameBlock(DARWIN_PROPS_SIG,text)

    @property
    def consoleCodePage(self)->typing.Optional[int]:
        """
        code page for the console (ConsoleFEDataBlock)
        """
        body=self.getExtraBlock(CONSOLE_FE_PROPS_SIG)
        return None if body is None else int(struct.unpack_from('<I',body)[0])
    @consoleCodePage.setter
    def consoleCodePage(self,codePage:typing.Optional[int])->None:
        self.setExtraBlock(CONSOLE_FE_PROPS_SIG,
            None if codePage is None else struct.pack('<I',codePage))

    @property
    def console(self)->typing.Optional[ConsoleData]:
        """
        console window properties (ConsoleDataBlock)
        """
        body=self.getExtraBlock(CONSOLE_PROPS_SIG)
        return None if body is None else _unpackConsole(body)
    @console.setter
    def console(self,console:typing.Optional[ConsoleData])->None:
        self.setExtraBlock(CONSOLE_PROPS_SIG,
            None if console is None else _packConsole(console))

    @property
    def knownFolderId(self)->typing.Optional[uuid.UUID]:
        """
        known folder the target is relative to
        """
        body=self.getExtraBlock(KNOWN_FOLDER_PROPS_SIG)
        return None if body is None else uuid.UUID(bytes_le=body[:16])

    @property
    def knownFolderOffset(self)->typing.Optional[int]:
        """
        offset into the IDList of the first item after the known folder
        """
        body=self.getExtraBlock(KNOWN_FOLDER_PROPS_SIG)
        return None if body is None \
            else int(struct.unpack_from('<I',body,16)[0])

    def setKnownFolder(
        self,folderId:typing.Optional[uuid.UUID],offset:int=0)->None:
        """
        :param folderId: the known folder (None to remove)
        :param offset: IDList offset of the first item after the folder
        """
        self.setExtraBlock(KNOWN_FOLDER_PROPS_SIG,None if folderId is None
            else folderId.bytes_le+struct.pack('<I',offset))

    @property
    def specialFolderId(self)->typing.Optional[int]:
        """ CSIDL of the special folder the target is relative to """
        body=self.getExtraBlock(SPECIAL_FOLDER_PROPS_SIG)
        return None if body is None \
            else int(struct.unpack_from('<I',body)[0])

    @property
    def specialFolderOffset(self)->typing.Optional[int]:
        """ offset into the IDList of the first item after the folder """
        body=self.getExtraBlock(SPECIAL_FOLDER_PROPS_SIG)
        return None if body is None \
            else int(struct.unpack_from('<I',body,4)[0])

    def setSpecialFolder(self,
        folderId:typing.Optional[int],
        offset:int=0
        )->None:
        """
        :param folderId: the CSIDL (None to remove)
        :param offset: IDList offset of the first item after the folder
        """
        self.setExtraBlock(SPECIAL_FOLDER_PROPS_SIG,None if folderId is None
            else struct.pack('<II',folderId,offset))

    @property
    def shimLayerName(self)->typing.Optional[str]:
        """ name of the application compatibility shim layer """
        body=self.getExtraBlock(SHIM_PROPS_SIG)
        return None if body is None else _cstr(body,0,True)
    @shimLayerName.setter
    def shimLayerName(self,name:typing.Optional[str])->None:
        self.setExtraBlock(SHIM_PROPS_SIG,
            None if name is None else name.encode('utf-16-le')+b'\x00\x00')

    @property
    def propertyStore(self)->typing.Optional[bytes]:
        """ raw serialized property store ([MS-PROPSTORE]) """
        return self.getExtraBlock(PROPERTY_STORE_PROPS_SIG)
    @propertyStore.setter
    def propertyStore(self,store:typing.Optional[bytes])->None:
        self.setExtraBlock(PROPERTY_STORE_PROPS_SIG,store)

    @property
    def vistaIdList(self)->typing.Optional[bytes]:
        """ alternate raw IDList used by Vista and above """
        return self.getExtraBlock(VISTA_AND_ABOVE_IDLIST_PROPS_SIG)
    @vistaIdList.setter
    def vistaIdList(self,idList:typing.Optional[bytes])->None:
        self.setExtraBlock(VISTA_AND_ABOVE_IDLIST_PROPS_SIG,idList)

    @property
    def tracker(self)->typing.Optional[TrackerData]:
        """ distributed link tracking information """
        body=self.getExtraBlock(TRACKER_PROPS_SIG)
        if body is None or len(body)<0x58:
            return None
        machine=_cstr(body[8:24],0)
        g=[uuid.UUID(bytes_le=body[24+16*i:40+16*i]) for i in range(4)]
        return TrackerData(machine,g[0],g[1],g[2],g[3])
    @tracker.setter
    def tracker(self,tracker:typing.Optional[TrackerData])->None:
        if tracker is None:
            self.setExtraBlock(TRACKER_PROPS_SIG,None)
            return
        self.setExtraBlock(TRACKER_PROPS_SIG,struct.pack('<II',0x58,0)\
            +tracker.machineId.encode(_ANSI,'replace')[:15].ljust(16,b'\x00')\
            +b''.join(g.bytes_le for g in (tracker.volumeDroid,
                tracker.fileDroid,tracker.volumeDroidBirth,
                tracker.fileDroidBirth)))

    @property
    def hotKeyVirtualKey(self)->int:
        """ virtual key code of the hotkey (0 if none) """
        return self.hotKey&0xFF

    @property
    def hotKeyModifiers(self)->int:
        """ HOTKEYF_* bits of the hotkey """
        return (self.hotKey>>8)&0xFF

    def setHotKey(self,virtualKey:int,modifiers:int=0)->None:
        """
        :param virtualKey: virtual key code (0 to clear)
        :param modifiers: HOTKEYF_SHIFT|HOTKEYF_CONTROL|HOTKEYF_ALT
        """
        self.hotKey=(virtualKey&0xFF)|((modifiers&0xFF)<<8)

    @property
    def idListItems(self)->typing.List[bytes]:
        """ the individual ItemIDs of the LinkTargetIDList """
        items:typing.List[bytes]=[]
        idList=self.shellItemId or b''
        offs=0
        while offs+2<=len(idList):
            size=struct.unpack_from('<H',idList,offs)[0]
            if size<3:
                break
            items.append(idList[offs+2:offs+size])
            offs+=size
        return items

    @staticmethod
    def _pathFromIdList(idList:bytes)->typing.Optional[str]:
        """
        Best-effort path from a LinkTargetIDList (uses the 8.3 names)

        :param idList: the raw IDList (without the leading size)
        """
        parts:typing.List[str]=[]
        offs=0
        while offs+2<=len(idList):
            size=struct.unpack_from('<H',idList,offs)[0]
            if size<3:
                break
            item=idList[offs+2:offs+size]
            offs+=size
            kind=item[0]&0x70
            if kind==0x20: # volume, eg "C:\"
                parts.append(_cstr(item,1).rstrip('\\'))
            elif kind==0x30 and len(item)>12: # file or directory
                parts.append(_cstr(item,12))
        if len(parts)<2:
            return None
        return '\\'.join(parts)

    # ---- the target ----

    def getTarget(self)->typing.Optional[FilePath]:
        """
        Get the link target, or None if it has no filesystem path
        (for instance, a link to the control panel)

        NOTE: targetPath and uncPath are the raw strings stored in the file
        """
        environmentTarget=self.environmentTarget
        if environmentTarget and (
            self.flags.preferEnvironmentPath or not self.targetPath):
            return FilePath(_expandWindowsEnvironment(environmentTarget))
        if self.targetPath:
            return FilePath(self.targetPath)
        if self.relativePath:
            base=FilePath('.')
            if self.linkFilename is not None:
                base=self.linkFilename.parent
            return FilePath(cleanup(
                self.relativePath,str(base.absolute())))
        return None

    def getPath(self)->typing.Optional[FilePath]:
        """
        Same as getTarget()
        """
        return self.getTarget()

    @property
    def path(self)->typing.Optional[FilePath]:
        """
        Same as getTarget()
        """
        return self.getTarget()

    def setTarget(self,
        target:UrlCompatible,
        isDirectory:bool=False,
        fileLength:int=0
        )->None:
        """
        Point the link somewhere else

        :param target: the path (or UNC path) to point to
        :param isDirectory: whether the target is a directory
        :param fileLength: size of the target file (0 for directories)
        """
        text=target if isinstance(target,str) else asFileString(target)
        if text.startswith('\\\\?\\UNC\\'):
            text='\\\\'+text[8:]
        elif text.startswith('\\\\?\\'):
            text=text[4:]
        if _WINDOWS_PATH.match(text):
            text=text.replace('/','\\')
        else:
            text=str(asFilePath(text).absolute())
        self.shellItemId=None
        self.flags.value&=~_FORCE_NO_LINK_INFO
        self.targetPath=text
        self.uncPath=text if text.startswith('\\\\') else None
        self.fileAttr.targetIsDir=isDirectory
        self.fileLength=0 if isDirectory else fileLength

    @staticmethod
    def create(
        target:UrlCompatible,
        description:typing.Optional[str]=None,
        arguments:typing.Optional[str]=None,
        workingDirectory:typing.Optional[str]=None,
        iconFile:typing.Optional[str]=None,
        iconNumber:int=0
        )->'WindowsLnkFormat':
        """
        Create a new link in memory (use save() to write it).
        Works on any operating system.

        If the target exists locally, its type and size are recorded.

        :param target: the path (or UNC path) to point to
        :param description: description of the link
        :param arguments: command line arguments
        :param workingDirectory: the working directory
        :param iconFile: file holding the icon
        :param iconNumber: index of the icon in iconFile
        """
        lnk=WindowsLnkFormat()
        isDir=False
        size=0
        try:
            p=asFilePath(target).pathlibPath
            isDir=p.is_dir()
            size=0 if isDir else p.stat().st_size
        except OSError: # not reachable from here (eg. a windows path)
            pass
        lnk.setTarget(target,isDir,size)
        lnk.description=description
        lnk.commandLine=arguments
        lnk.workingDirectory=workingDirectory
        lnk.iconFile=iconFile
        lnk.iconNumber=iconNumber
        return lnk

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

    def getHotKey(self)->int:
        """
        The raw hotkey value (low byte=virtual key, high byte=modifiers)
        """
        return self.hotKey

    # ---- saving ----

    def _buildLinkInfo(self)->typing.Optional[bytes]:
        """
        Build a LinkInfo section from the target path
        """
        target=self.targetPath
        if not target:
            return None
        headerSize=0x24
        if target.startswith('\\\\'):
            parts=target[2:].split('\\',2)
            netName='\\\\'+'\\'.join(parts[:2])
            suffix=parts[2] if len(parts)>2 else ''
            netBlock=struct.pack('<5I',0x14+len(_ansiz(netName)),
                0x2 if self.networkProviderType else 0,0x14,0,
                self.networkProviderType)+_ansiz(netName)
            networkOffset=headerSize
            suffixOffset=networkOffset+len(netBlock)
            suffixUnicode=suffixOffset+len(_ansiz(suffix))
            body=netBlock+_ansiz(suffix)+_unicodez(suffix)
            fields=(0,0,networkOffset,suffixOffset,0,suffixUnicode)
            infoFlags=0x2
        else:
            label=_ansiz(self.volumeLabel)
            volume=struct.pack('<4I',
                0x10+len(label),self.driveType or 3,
                self.driveSerialNumber,0x10)+label
            volumeOffset=headerSize
            localOffset=volumeOffset+len(volume)
            suffixOffset=localOffset+len(_ansiz(target))
            localUnicode=suffixOffset+1
            suffixUnicode=localUnicode+len(_unicodez(target))
            body=volume+_ansiz(target)+b'\x00'+_unicodez(target)+b'\x00\x00'
            fields=(volumeOffset,localOffset,0,suffixOffset,
                localUnicode,suffixUnicode)
            infoFlags=0x1
        header=struct.pack('<9I',headerSize+len(body),headerSize,infoFlags,
            *fields)
        return header+body

    def toBytes(self)->bytes:
        """
        Get the contents of the lnk file
        """
        linkInfo=None if self.flags.forceNoLinkInfo else self._buildLinkInfo()
        flags=_IS_UNICODE
        if self.shellItemId:
            flags|=_HAS_ID_LIST
        if linkInfo:
            flags|=_HAS_LINK_INFO
        strings:typing.List[bytes]=[]
        for mask,value in (
            (_HAS_NAME,self.description),
            (_HAS_RELATIVE_PATH,self.relativePath),
            (_HAS_WORKING_DIR,self.workingDirectory),
            (_HAS_ARGUMENTS,self.commandLine),
            (_HAS_ICON_LOCATION,self.iconFile)): # noqa: E129
            #
            if value:
                flags|=mask
                encoded=value.encode('utf-16-le','surrogatepass')
                strings.append(struct.pack('<H',len(encoded)//2)+encoded)
        flags|=self.flags.value&~_MANAGED_FLAGS # keep flags we don't manage
        for sig,mask in _BLOCK_FLAGS.items():
            if self.getExtraBlock(sig) is None:
                flags&=~mask
            else:
                flags|=mask
        now=_filetimeNow()
        header=bytes(WindowsLnkFormat.START_BYTES) \
            +bytes(WindowsLnkFormat.GUID_BYTES) \
            +struct.pack('<IIQQQIiIHHII',
                flags,int(self.fileAttr) or FILE_ATTRIBUTE_NORMAL,
                self.creationTime or now,self.accessTime or now,
                self.modificationTime or now,
                self.fileLength,self.iconNumber,self.showWindowOptions,
                self.hotKey,0,0,0)
        out=[header]
        if self.shellItemId:
            out.append(struct.pack('<H',len(self.shellItemId)))
            out.append(self.shellItemId)
        if linkInfo:
            out.append(linkInfo)
        out.extend(strings)
        out.append(self.extraData)
        return b''.join(out)

    def save(self,
        saveAsFilename:typing.Optional[UrlCompatible]=None,
        noClobberFile:bool=True
        )->FilePath:
        """
        Save the link to a file

        :param saveAsFilename: where to save (default is the loaded file)
        :param noClobberFile: safeguard to never overwrite
            an actual file with a link
        :return: the filename actually written
        """
        dest:typing.Optional[FilePath]=self.linkFilename
        if saveAsFilename is not None:
            dest=asFilePath(saveAsFilename)
        if dest is None:
            if not self.targetPath:
                raise LinkException('ERR: No filename to save link as')
            dest=FilePath(
                self.targetPath.replace('/','\\').rsplit('\\',1)[-1]+'.lnk')
        if noClobberFile \
            and dest.exists() \
            and not WindowsLnkFormat.isLink(dest):
            idx=1
            while True:
                fn=FilePath('%s_%03d'%(dest,idx))
                if not fn.exists() or WindowsLnkFormat.isLink(fn):
                    break
                idx+=1
            dest=fn
        dest.pathlibPath.write_bytes(self.toBytes())
        self.linkFilename=dest
        return dest

    @staticmethod
    def isLink(
        filename:typing.Optional[UrlCompatible],
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
        filename:typing.Optional[UrlCompatible],
        fileBuffer:typing.Optional[bytes]=None
        )->bool:
        """
        determine if the given file is a windows shortcut

        if filename is None, base the determination soley on the data buffer

        if fileBuffer is None, will open the filename ourselves

        :param filename: file to check
        :param fileBuffer: the first bytes of the file
        """
        path=None if filename is None else asFilePath(filename)
        if path is not None and path.extension!='lnk':
            return False
        if fileBuffer is None:
            if path is None or not path.is_file():
                return False
            with path.pathlibPath.open('rb') as f:
                fileBuffer=f.read(
                    len(WindowsLnkFormat.START_BYTES)\
                    +len(WindowsLnkFormat.GUID_BYTES))
        expected=bytes(
            WindowsLnkFormat.START_BYTES+WindowsLnkFormat.GUID_BYTES)
        return fileBuffer[:len(expected)]==expected


def cmdline(args:typing.Iterable[str])->int:
    """
    Run the command line

    :param args: command line arguments (WITHOUT the filename)
    """
    args=list(args)
    if not args:
        print('Usage:')
        print('  windowsLnkFormat.py file.lnk [file.lnk ...]')
        return 1
    for arg in args:
        print(str(WindowsLnkFormat(arg)))
    return 0


if __name__=='__main__':
    import sys
    sys.exit(cmdline(sys.argv[1:]))

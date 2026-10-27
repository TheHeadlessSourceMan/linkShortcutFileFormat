"""
Deprecated/untested shortcut tools kept for reference
"""
from typing import Optional

        
def makeShortcutsRelative(path:str,recursive:bool=False,constrainTo:Optional[str]=None,dryRun:bool=False)->None:
    """
    Convert shortcuts from absolute to relative (if possible)

    :param path: where to start searching for shortcuts
    :param recursive: True/False whether to search sub-directories
    :param constrainTo: only change targets starting with this path (default is the drive of path)
    :param dryRun: True/False only report what would change
    """
    linkFinderGenerator=findAll(path,yeild_files=False,yeild_shortcuts=True,recursive=recursive)
    if constrainTo is None or constrainTo=='': # must at least be in the same drive letter
        constrainTo=path.split('\\',1)[0].upper()
    else:
        constrainTo=constrainTo.split('\\',1)
        constrainTo[0]=constrainTo[0].upper()
        constrainTo='\\'.join(constrainTo)
    for sc in linkFinderGenerator:
        sc=winshell.shortcut(sc)
        fromPath=str(sc.lnk_filepath)
        toPath=str(sc.path)
        if toPath.find(constrainTo)==0: # Make sure this is a path we are allowed to make relative (also verifies that it doesn't start with %CD%)
            print('changing...',fromPath+' => '+toPath)
            fromPath=sc.lnk_filepath.split('\\')[0:-1]
            toPath=sc.path.split('\\')
            fromPath[0]=fromPath[0].upper()
            toPath[0]=toPath[0].upper()
            while len(fromPath)>0 and len(toPath)>0 and fromPath[0]==toPath[0]:
                fromPath.pop(0)
                toPath.pop(0)
            fromPath=['..' for i in fromPath]
            fromPath.insert(0,r'%CD%')
            newPath=('\\'.join(fromPath))+'\\'+('\\'.join(toPath))
            print('Changing to:',newPath)
            if not dryRun:
                sc.path=newPath # chop path and prefix with %CD%
                sc.write()
        else:
            if fromPath.startswith(r'%CD%'):
                print('already relative:',fromPath)
            else:
                print('skipping:',fromPath+' => '+toPath)
                print('\t(it must start with "'+constrainTo+'")')

def makeShortcutsAbsolute(shortcut:str,dryRun:bool=False)->None:
    """
    Convert shortcuts from relative to absolute
    
    TODO: Not yet tested!!!

    :param shortcut: path of the shortcut to convert
    :param dryRun: True/False only report what would change
    """
    sc=winshell.shortcut(shortcut)
    if sc.startswith('%CD%'):
        newPath=lnk_filepath.rsplit('\\',1)[0]+sc.path[4:] # replace %CD% prefix with lnk file's directory
        if not dryRun:
            sc.path=newPath
            sc.write()
            
def convertShortcutToSymlink(shortcut:str)->None:
    """
    Attempt to convert a lnk file into a NTFS "Junction"
    (equivalent to a symlink on real OSes)
    
    Requires Vista or greater:
        http://msdn.microsoft.com/en-us/library/aa363866(VS.85).aspx
    
    UNTESTED!!!!!
    Also, may not work correctly for all things, for example shortcuts with parameters.

    :param shortcut: path of the lnk file to convert
    """
    import win32file
    sc=winshell.shortcut(shortcut) # http://winshell.readthedocs.org/en/latest/shortcuts.html
    win32file.CreateSymbolicLink(sc.path,sc.lnk_filepath,1) # http://docs.activestate.com/activepython/2.7/pywin32/win32file__CreateSymbolicLink_meth.html

        
if False:
    """
    This is another way
    """
    import winshell
    winshell.CreateShortcut (
      Path=os.path.join (winshell.desktop (), "PythonI.lnk"),
      Target=sys.executable,
      Icon=(sys.executable, 0),
      Description="Python Interpreter"
    )
if False:
# originally translated to python from:
    #    http://www.codeproject.com/Articles/7030/Utility-for-creating-Link-shortcut
    #
    #    NOT tested!
    def CreateLink(nFolder):
        """
        :param nFolder: CSIDL of the special folder to create the link in
        """
        UpdateData(TRUE) 
        #Check for empty strings ...
        if(m_strItem.IsEmpty() || m_strFile.IsEmpty())
            AfxMessageBox("Please,enter the Menu Item and File name correctly.")
            return    
        #File system directory that contains the directories for the
        #common program groups that appear on the Start menu for all users.
        LPITEMIDLIST pidl
        # Get a pointer to an item ID list that
        # represents the path of a special folder
        HRESULT hr = SHGetSpecialFolderLocation(NULL, nFolder, &pidl)
        # Convert the item ID list's binary
        # representation into a file system path
        char szPath[_MAX_PATH]
        BOOL f = SHGetPathFromIDList(pidl, szPath)
        # Allocate a pointer to an IMalloc interface
        LPMALLOC pMalloc
        # Get the address of our task allocator's IMalloc interface
        hr = SHGetMalloc(&pMalloc)
        # Free the item ID list allocated by SHGetSpecialFolderLocation
        pMalloc->Free(pidl)
        # Free our task allocator
        pMalloc->Release()
        CString szLinkName = m_strItem
        szLinkName+=".lnk"
        CString m_szCurrentDirectory = szPath 
        szLinkName= m_szCurrentDirectory+"\\"+szLinkName
        HRESULT hres = NULL
        IShellLink* psl = NULL
        # Get a pointer to the IShellLink interface. 
        hres = CoCreateInstance(CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, IID_IShellLink, reinterpret_cast<void**>(&psl))
        if SUCCEEDED(hres):
            IPersistFile* ppf = NULL 
            # Set the path to the shortcut target
            psl->SetPath(m_strFile) 
            # Query IShellLink for the IPersistFile interface for saving 
            #the shortcut in persistent storage. 
            hres = psl->QueryInterface(IID_IPersistFile, reinterpret_cast<void**>(&ppf)) 
            if SUCCEEDED(hres):
                WCHAR wsz[MAX_PATH] 
                # Ensure that the string is ANSI. 
                MultiByteToWideChar(CP_ACP, 0, szLinkName, -1, wsz, MAX_PATH) 
                # Save the link by calling IPersistFile::Save. 
                hres = ppf->Save(wsz, TRUE) 
                ppf->Release() 
            psl->Release() 
        UpdateData(FALSE) 
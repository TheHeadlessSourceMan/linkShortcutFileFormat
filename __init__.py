"""
Wraps a windows link file of any kind.

If a proper file is given, will be able to handle it gracefully in most
cases, but beware of what you have before operating on it.
(use WindowsLink.isLink())

Also handles special case "Folder Shortcuts"
(not the same as a shortcut to a folder)  For the scoop on that, see:
    https://superuser.com/questions/456399/what-different-types-of-shortcut-are-there/639967#639967

For non-windows systems, also provides direct access to the
windows .lnk file format.

@supports: pyformatgenie
"""
from .linkExceptions import *
from .linkTypes import *
from .windowsLnkFormat import *
from .windowsLinks import *
from .findReplace import *
from .fixer import *

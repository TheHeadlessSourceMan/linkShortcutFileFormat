#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Exceptions associated with links
"""

class LinkException(Exception):
    """
    Base class used for announcing errors concerning file links
    """
    def __init__(self,msg):
        """
        Create the exception
        """
        Exception.__init__(self,msg)


class RecursiveLinkException(LinkException):
    """
    Following a link to its destination would result in an infinite loop
    """
    def __init__(self,problemPath):
        fullPath=('\n  => '.join(['"'+path+'"' for path in problemPath]))
        LinkException.__init__(self,'ERR: Recursive link detected:\n  => '+fullPath)


class NotALinkException(LinkException):
    """
    Tried to address something that is not a link
    """
    def __init__(self,linkPath):
        LinkException.__init__(self,'ERR: Not a valid link "'+linkPath+'"')


class BrokenLinkException(LinkException):
    """
    The target of a link has gone missing
    """
    def __init__(self,linkPath):
        LinkException.__init__(self,'ERR: Broken link "'+linkPath+'"')


def cmdline(args):
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
                else:
                    print(('ERR: unknown argument "'+arg[0]+'"'))
            else:
                print(('ERR: unknown argument "'+arg+'"'))
    if printhelp:
        print('Usage:')
        print('  linkExceptions.py [options]')
        print('Options:')
        print('   NONE')


if __name__=='__main__':
    import sys
    cmdline(sys.argv[1:])

#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Types of links
"""

LINKTYPE_ANY=-1 # Used for searching.  You will never encounter a file of LINKTYPE_ANY.
LINKTYPE_NONLINK=0
LINKTYPE_SHORTCUT=1
LINKTYPE_FOLDER_SHORTCUT=2
LINKTYPE_JUNCTION=3
LINKTYPE_HARD_LINK=4
LINKTYPE_SOFT_LINK=5
LINKTYPE_SYMBOLIC_LINK=6

LINK_TYPES=[
    'Not a link', # 0
    'Shortcut', # 1
    'Folder Shortcut', # 2
    'Junction', # 3
    'Hard Link', # 4
    'Soft Link', # 5
    'Symbolic Link', # 6
    ]
    
def LinkTypeOf(something):
    """
    Get the link type of something.
    
    :param something: can be
        * class with a linkType member (e.g. a Link object)
        * an integer link type
        * a bool, interpreted as True=LINKTYPE_ANY and False=LINKTYPE_NONLINK
        * a string representing:
            * an integer link type
            * a bool
            * a name similar to of one of the linktype constant names
    """
    if hasattr(something,'linkType'):
        return something.linkType
    if isinstance(something,bool):
        if something:
            return LINKTYPE_ANY
        return LINKTYPE_NONLINK
    if isinstance(something,int):
        if something>LINKTYPE_SYMBOLIC_LINK or something<LINKTYPE_ANY:
            raise Exception('Link type out of bounds!')
        return something
    if not isinstance(something,str) or not str:
        raise Exception('Unable to convert this item to a link type')
    something=something.replace('_','').replace(' ','').lower().replace('linktype','').replace('link','')
    if something in ('any','-1'):
        return LINKTYPE_ANY
    if something in ('non','0'):
        return LINKTYPE_NONLINK
    if something in ('shortcut','1'):
        return LINKTYPE_SHORTCUT
    if something in ('folder','foldershortcut','2'):
        return LINKTYPE_FOLDER_SHORTCUT
    if something in ('junction','3'):
        return LINKTYPE_JUNCTION
    if something in ('hard','4'):
        return LINKTYPE_HARD_LINK
    if something in ('soft','5'):
        return LINKTYPE_SOFT_LINK
    if something in ('symbolic','6'):
        return LINKTYPE_SYMBOLIC_LINK
    if something[0] in ('t','y'):
        return LINKTYPE_ANY
    return LINKTYPE_NONLINK
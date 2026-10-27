#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Run unit tests

See:
    http://pyunit.sourceforge.net/pyunit.html
"""
import typing
import unittest
import os
import shutil
from PIL import Image
from linkShortcutFileFormat import (
    createLink,findBrokenShortcuts,
    LINKTYPE_FOLDER_SHORTCUT,LINKTYPE_SHORTCUT,
    findAll,WindowsLink)
from linkShortcutFileFormat.windowsUtils import nextAvailableFilename


def compareImage(img1:Image.Image,img2:Image.Image)->bool:
    """
    Check whether two PIL images are identical

    :param img1: first image
    :param img2: second image
    """
    import PIL.ImageChops
    return PIL.ImageChops.difference(img1,img2).getbbox() is None


__HERE__=os.path.abspath(__file__).rsplit(os.sep,1)[0]+os.sep
results_dir=__HERE__+'results'+os.sep
class Test(unittest.TestCase):
    """
    Run unit test
    """

    def setUp(self)->None:
        """
        Start each test with an empty results directory
        """
        os.chdir(__HERE__)
        try:
            shutil.rmtree(results_dir)
        except Exception:
            pass
        os.mkdir(results_dir)

    def tearDown(self)->None:
        """
        Leave results in place for inspection
        """
        pass # shutil.rmtree(results_dir)

    def toFolderShortcut(self)->None:
        """
        Test converting a shortcut into a folder shortcut
        """
        print()
        required:typing.List[str]=['linkToFolder.lnk','targetFolder']
        f='linkToFolder.lnk'
        shutil.copy2(__HERE__+f,results_dir+f)
        f='targetFolder'
        shutil.copytree(__HERE__+f,results_dir+f)
        #
        lnk=WindowsLink(results_dir+'linkToFolder.lnk')
        print('attemting to change shortcut to folder shortcut')
        lnk.changeType(LINKTYPE_FOLDER_SHORTCUT)
        lnk2=WindowsLink(lnk.path)
        print('   ',lnk2.path)
        print('did it work?')
        assert lnk2.linkType==LINKTYPE_FOLDER_SHORTCUT
        print('   ',results_dir+'targetFolder')
        print('   ',lnk2.targetPath)
        assert lnk2.targetPath==results_dir+'targetFolder'

    def fromFolderShortcut(self)->None:
        """
        Test creating a folder shortcut and converting it back into a shortcut
        """
        print()
        f='targetFolder'
        shutil.copytree(__HERE__+f,results_dir+f)
        print('creating new folder shortcut')
        lnk=createLink(
            results_dir+f,
            linkType=LINKTYPE_FOLDER_SHORTCUT,
            shortcutName=results_dir+'testFolderShortcut')
        print('   ',lnk.path)
        print('    - links to -')
        print('   ',lnk.targetPath)
        assert results_dir+f==lnk.targetPath
        print('attempting to change folder shortcut into shortcut')
        lnk.changeType(LINKTYPE_SHORTCUT)
        lnk2=WindowsLink(lnk.path)
        print('did it work?')
        assert lnk2.linkType==LINKTYPE_SHORTCUT
        print('   ',results_dir+'targetFolder')
        print('   ',lnk2.targetPath)
        assert lnk2.targetPath==results_dir+'targetFolder'
        assert str(lnk2) # verify __repr__() function

    def makeShortcutRelative(self)->None:
        """
        Test making a shortcut relative (not implemented)
        """
        assert False

    def makeShortcutAbsolute(self)->None:
        """
        Test making a shortcut absolute (not implemented)
        """
        assert False

    def shortcutToSymlink(self)->None:
        """
        Test converting a shortcut to a symlink (not implemented)
        """
        assert False

    def findBrokenShortcuts(self)->None:
        """
        Test finding broken shortcuts (not implemented)
        """
        broke=findBrokenShortcuts('.',recursive=True)
        # TODO:
        assert False

    def fixBrokenShortcuts(self)->None:
        """
        Test fixing broken shortcuts (not implemented)
        """
        fixBrokenShortcuts(path,recursive=True,dryRun=True)
        assert False

    def finalPath(self)->None:
        """
        Test resolving links to their final target
        """
        print()
        links=[ # (linkName, desiredTargetFilename)
            (os.path.abspath('targetFile.txt'),'targetFile.txt'),
            ('linkToFile.lnk','targetFile.txt'),
            ('linkToFolder.lnk','targetFolder'),
            ('linkToFile','targetFile.txt'),
            ('linkToFolder','targetFolder'),
            ('linkToLink.lnk','targetFile.txt'),
            ]
        for linkName,desiredTargetFilename in links:
            desiredTargetFilename=os.path.abspath(desiredTargetFilename)
            path=finalPath(linkName)
            print(linkName,':\n\t',path,'\n\t',desiredTargetFilename)
            assert path==desiredTargetFilename

    def icons(self)->None:
        """
        Test reading a shortcut's icon
        """
        print()
        linkName='linkToFile'
        iconFile=r'%SystemRoot%\system32\SHELL32.dll'
        iconNumber=43
        link=WindowsLnkFormat(linkName)
        print(linkName,':\n\t',link.iconFile+':'+str(link.iconNumber))
        assert link.iconFile==iconFile
        assert link.iconNumber==iconNumber

    def comments(self)->None:
        """
        Test reading a shortcut's comment
        """
        print()
        linkName='linkToFile'
        comment=r'SAMPLE COMMENT'
        link=WindowsLnkFormat(linkName)
        print(linkName,':\n\t',link.comment)
        assert link.comment==comment

    def osEnquote(self)->None:
        """
        Test quoting of paths containing spaces
        """
        print()
        enquotes:typing.List[typing.Tuple[
            typing.Optional[str],typing.Optional[str]]]\
            =[ # (input,expected)
            (None,None),
            (r'hello.txt',r'hello.txt'),
            (r'hello world.txt',r'"hello world.txt"'),
            (r'"hello world.txt"',r'"hello world.txt"'),
            #(r'hello "world".txt',r'"hello \"world\".txt"'), #TODO: not working! # noqa: E501
        ]
        for input,expected in enquotes:
            quoted=osEnquote(input)
            print(input)
            print(expected)
            print(quoted)
            print()
            assert quoted==expected

    def nextAvailableFilename(self)->None:
        """
        Test generating unused filenames
        """
        print()
        # create needed files
        create=['B.txt','C.txt','C 1.txt']
        for f in create:
            f=results_dir+f
            print('Create:',f)
            f=open(f,'w')
            f.write('x')
            f.close()
        os.mkdir(results_dir+'x')
        items=[ # (input,expected)
            (r'A.txt',r'A.txt'),
            (r'B.txt',r'B 1.txt'),
            (r'C.txt',r'C 2.txt'),
            (r'x\\',r'x 1'),
        ]
        for input,expected in items:
            input=results_dir+input
            expected=results_dir+expected
            print(input)
            print(expected)
            result=nextAvailableFilename(input,ignore='junk')
            print(result)
            assert result==expected

    def find(self)->None:
        """
        Test searching for files and links
        """
        print()
        tests:typing.List[typing.Tuple[
            typing.List[str],typing.List[typing.Any]]]=[ # ([results],[params])
            ([
                r'folderShortcut',
                r'linkToFile.lnk',
                r'linkToFolder.lnk',
                r'linkToLink.lnk',
                r'results',
                r'targetFile.txt',
                r'targetFolder',
                r'test.py',
                r'__init__.py',
                r'linkToFile.lnk',
                r'linkToLink.lnk',
                r'targetFile.txt',
                r'test.py',
                r'__init__.py',
                r'targetFolder\targetFolderFile.txt',
                r'targetFolder\targetFolderFile.txt'],
                [None,MATCH_TYPE_GLOB,True,True,True,True,True])
            ]
        for t in tests:
            print(t)
            actual=findAll(__HERE__,*t[1])
            actual=[x.path for x in actual]
            print(actual)
            print()
            assert len(actual)==len(t[0])
            for item in t[0]:
                assert os.path.abspath(item) in actual

    def createShortcut(self)->None:
        """
        Test creating shortcuts without overwriting existing ones
        """
        print()
        f='targetFile.txt'
        shutil.copy2(__HERE__+f,results_dir+f)
        print('creating new shortcut')
        lnk=createLink(results_dir+f,linkType=LINKTYPE_SHORTCUT)
        print('   ',lnk.path)
        print('   - points to -')
        print('   ',lnk.targetPath)
        assert results_dir+f+'.lnk'==lnk.path
        assert lnk.targetPath==results_dir+f
        print('Now make sure it doesn\'t overwrite')
        lnk2=createLink(results_dir+f,linkType=LINKTYPE_SHORTCUT)
        assert results_dir+f+' 1.lnk'==lnk2.path
        assert lnk2.targetPath==results_dir+f

    def iconLoader(self)->None:
        """
        Test loading icons from files and file types
        """
        print()
        actual=iconImage(__HERE__+'defaulticon.ico')
        print('SHELL32.dll:0')
        assert compareImage(actual,iconImage('SHELL32.dll:0'))
        print(':0')
        assert compareImage(actual,iconImage(':0'))
        print('""')
        assert compareImage(actual,iconImage(''))
        print(':1')
        assert compareImage(actual,iconImage(':1',index_plus_one=False))
        print('someMissingExtension')
        ico=iconForFiletype('x.someMissingExtension')
        ico.save('bogus.ico')
        # test error conditions
        try:
            x=iconImage('missing.dll')
            assert False
        except FileNotFoundError:
            pass
        try:
            x=iconImage('./missing.dll')
            assert False
        except FileNotFoundError:
            pass

def suite(tests:Optional[Sequence[str]]=None)->unittest.TestSuite:
    """
    Combine unit tests into an entire suite

    :param tests: names of tests to include (currently unused)
    """
    testSuite = unittest.TestSuite()
    #testSuite.addTest(Test("osEnquote"))
    #testSuite.addTest(Test("nextAvailableFilename"))
    #testSuite.addTest(Test("createShortcut"))
    #testSuite.addTest(Test("finalPath"))
    #testSuite.addTest(Test("icons"))
    #testSuite.addTest(Test("comments"))
    #testSuite.addTest(Test("find"))
    #testSuite.addTest(Test("toFolderShortcut"))
    testSuite.addTest(Test("fromFolderShortcut"))
    #testSuite.addTest(Test("iconLoader"))
    return testSuite


def run(
    tests:Optional[Sequence[str]]=None,
    output:Optional[str]=None,
    verbosity:int=2,
    failfast:bool=False
    )->None:
    """
    run the test suite

    :param tests: names of tests to run
    :param output: file to write results to (default stdout)
    :param verbosity: unittest verbosity level
    :param failfast: stop at the first failure
    """
    if output is None:
        output=sys.stdout
    else:
        output=open(output,'wb')
    runner=unittest.TextTestRunner(
        output,verbosity=verbosity,failfast=failfast)
    runner.run(suite(tests))


def cmdline(args:typing.Iterable[str])->int:
    """
    Run the command line

    :param args: command line arguments (WITHOUT the filename)
    """
    printhelp=False
    save=None
    tests:typing.List[str]=[]
    if not args:
        pass #printhelp=True
    else:
        for arg in args:
            if arg.startswith('-'):
                arg=[a.strip() for a in arg.split('=',1)]
                if arg[0] in ['-h','--help']:
                    printhelp=True
                elif arg[0]=='--save':
                    save=arg[1]
                else:
                    print('ERR: unknown argument "'+arg[0]+'"')
            else:
                tests.append(arg)
    if printhelp:
        print('Usage:')
        print('  test.py [options] [tests]')
        print('Options:')
        print('   --save=filename ............... save the test output to this file, rather than the console') # noqa: E501
        return -1
    run(tests,save)
    return 0


if __name__=='__main__':
    import sys
    cmdline(sys.argv[1:])

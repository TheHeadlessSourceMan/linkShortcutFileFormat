#!/usr/bin/env
# -*- coding: utf-8 -*-
"""
Run unit tests

See:
    http://pyunit.sourceforge.net/pyunit.html
"""
import os
import shutil
import struct
import sys
import typing
import unittest
from typing import Optional, Sequence
from PIL import Image
from paths import FilePath
from linkShortcutFileFormat import (
    createLink,findBrokenShortcuts,fixBrokenShortcuts,finalPath,
    LINKTYPE_FOLDER_SHORTCUT,LINKTYPE_SHORTCUT,
    MATCH_TYPE_GLOB,findAll,WindowsLink,WindowsLnkFormat)
from linkShortcutFileFormat.windowsUtils import (
    iconForFiletype, iconImage, nextAvailableFilename, osEnquote)


def compareImage(img1:Image.Image,img2:Image.Image)->bool:
    """
    Check whether two PIL images are identical

    :param img1: first image
    :param img2: second image
    """
    import PIL.ImageChops
    return PIL.ImageChops.difference(img1,img2).getbbox() is None


__HERE__ = FilePath(__file__).absolute().parent
results_dir = __HERE__ / 'results'


class Test(unittest.TestCase):
    """
    Run unit test
    """

    def setUp(self)->None:
        """
        Start each test with an empty results directory
        """
        os.chdir(str(__HERE__))
        try:
            shutil.rmtree(str(results_dir))
        except Exception:
            pass
        results_dir.pathlibPath.mkdir()

    def tearDown(self)->None:
        """
        Leave results in place for inspection
        """
        pass # shutil.rmtree(results_dir)

    def test_toFolderShortcut(self)->None:
        """
        Test converting a shortcut into a folder shortcut
        """
        print()
        f='linkToFolder.lnk'
        shutil.copy2(str(__HERE__/f),str(results_dir/f))
        f='targetFolder'
        shutil.copytree(str(__HERE__/f),str(results_dir/f))
        #
        lnk=WindowsLink(results_dir/'linkToFolder.lnk')
        print('attemting to change shortcut to folder shortcut')
        lnk.changeType(LINKTYPE_FOLDER_SHORTCUT)
        lnk2=WindowsLink(lnk.path)
        print('   ',lnk2.path)
        print('did it work?')
        self.assertEqual(lnk2.linkType, LINKTYPE_FOLDER_SHORTCUT)
        print('   ',results_dir/'targetFolder')
        print('   ',lnk2.targetPath)
        self.assertEqual(
            str(lnk2.targetPath), str(results_dir / 'targetFolder'))

    def test_fromFolderShortcut(self)->None:
        """
        Test creating a folder shortcut and converting it back into a shortcut
        """
        print()
        f='targetFolder'
        shutil.copytree(str(__HERE__/f),str(results_dir/f))
        print('creating new folder shortcut')
        lnk=createLink(
            results_dir/f,
            linkType=LINKTYPE_FOLDER_SHORTCUT,
            shortcutName=results_dir/'testFolderShortcut')
        assert lnk is not None
        print('   ',lnk.path)
        print('    - links to -')
        print('   ',lnk.targetPath)
        self.assertEqual(str(results_dir / f), str(lnk.targetPath))
        print('attempting to change folder shortcut into shortcut')
        lnk.changeType(LINKTYPE_SHORTCUT)
        lnk2=WindowsLink(lnk.path)
        print('did it work?')
        self.assertEqual(lnk2.linkType, LINKTYPE_SHORTCUT)
        print('   ',results_dir/'targetFolder')
        print('   ',lnk2.targetPath)
        self.assertEqual(
            str(lnk2.targetPath), str(results_dir / 'targetFolder'))
        self.assertTrue(str(lnk2))

    @unittest.skip('not implemented')
    def test_makeShortcutRelative(self)->None:
        """
        Test making a shortcut relative (not implemented)
        """
        pass

    @unittest.skip('not implemented')
    def test_makeShortcutAbsolute(self)->None:
        """
        Test making a shortcut absolute (not implemented)
        """
        pass

    @unittest.skip('not implemented')
    def test_shortcutToSymlink(self)->None:
        """
        Test converting a shortcut to a symlink (not implemented)
        """
        pass

    def test_findBrokenShortcuts(self)->None:
        """
        Test finding broken shortcuts (not implemented)
        """
        broken = list(findBrokenShortcuts(__HERE__, recursive=True))
        self.assertEqual(broken, [])

    def test_fixBrokenShortcuts(self)->None:
        """
        Test fixing broken shortcuts (not implemented)
        """
        fixBrokenShortcuts(__HERE__, recursive=True, dryRun=True)

    def test_finalPath(self)->None:
        """
        Test resolving links to their final target
        """
        print()
        links=[ # (linkName, desiredTargetFilename)
            (str(FilePath('targetFile.txt').absolute()),'targetFile.txt'),
            ('linkToFile.lnk','targetFile.txt'),
            ('linkToFolder.lnk','targetFolder'),
            ('linkToFile','targetFile.txt'),
            ('linkToFolder','targetFolder'),
            ('linkToLink.lnk','targetFile.txt'),
            ]
        for linkName,desiredTargetFilename in links:
            desiredTargetFilename=str(FilePath(desiredTargetFilename).absolute()) # noqa: E501
            path=finalPath(linkName)
            print(linkName,':\n\t',path,'\n\t',desiredTargetFilename)
            self.assertEqual(str(path.absolute()), desiredTargetFilename)

    def test_icons(self)->None:
        """
        Test reading a shortcut's icon
        """
        print()
        linkName='linkToFile'
        iconFile=r'%SystemRoot%\system32\SHELL32.dll'
        iconNumber=43
        link=WindowsLnkFormat(linkName)
        icon_file = str(link.iconFile)
        print(linkName,':\n\t',f'{icon_file}:{link.iconNumber}')
        self.assertEqual(link.iconFile, iconFile)
        self.assertEqual(link.iconNumber, iconNumber)

    def test_comments(self)->None:
        """
        Test reading a shortcut's comment
        """
        print()
        linkName='linkToFile'
        comment=r'SAMPLE COMMENT'
        link=WindowsLnkFormat(linkName)
        print(linkName,':\n\t',link.comment)
        self.assertEqual(link.comment, comment)

    def test_environmentTarget(self)->None:
        """Resolve EnvironmentVariableDataBlock paths according to its flag."""
        print()
        key='LINK_SHORTCUT_TEST_ROOT'
        oldValue=os.environ.get(key)
        try:
            os.environ[key]=str(results_dir)
            link=WindowsLnkFormat.create(results_dir/'targetFile.txt')
            link.environmentTarget=r'%LINK_SHORTCUT_TEST_ROOT%\\targetFile.txt'
            self.assertEqual(
                str(link.getTarget()),
                str(results_dir/'targetFile.txt'))
            loaded=WindowsLnkFormat()
            loaded.parse(link.toBytes())
            loaded.flags.value|=0x02000000
            self.assertEqual(
                str(loaded.getTarget()),
                str(results_dir/'targetFile.txt'))
            link.targetPath=r'%LINK_SHORTCUT_TEST_ROOT%\\fallback.txt'
            self.assertEqual(
                str(link.getTarget()),
                str(FilePath(link.targetPath)))
            link.flags.value|=0x02000000
            self.assertEqual(
                str(link.getTarget()),
                str(results_dir/'targetFile.txt'))
            link.environmentTarget=r'%LINK_SHORTCUT_UNKNOWN%\\target.txt'
            self.assertEqual(
                str(link.getTarget()),
                str(FilePath(link.environmentTarget)))
        finally:
            if oldValue is None:
                os.environ.pop(key,None)
            else:
                os.environ[key]=oldValue

    def test_invalidExtraDataSize(self)->None:
        """Reject an ExtraData block whose declared size exceeds the buffer."""
        with self.assertRaises(struct.error):
            parseExtraData=WindowsLnkFormat._parseExtraData # type: ignore
            parseExtraData(
                struct.pack('<II',12,0xA0000001)+b'bad')

    def test_osEnquote(self)->None:
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
            self.assertEqual(quoted, expected)

    def test_nextAvailableFilename(self)->None:
        """
        Test generating unused filenames
        """
        print()
        # create needed files
        create=['B.txt','C.txt','C 1.txt']
        for f in create:
            f=results_dir/f
            print('Create:',f)
            f.pathlibPath.write_text('x')
        (results_dir/'x').pathlibPath.mkdir()
        items=[ # (input,expected)
            (r'A.txt',r'A.txt'),
            (r'B.txt',r'B 1.txt'),
            (r'C.txt',r'C 2.txt'),
            (r'x',r'x 1'),
        ]
        for input,expected in items:
            input=results_dir/input
            expected=str(results_dir/expected)
            print(input)
            print(expected)
            result=nextAvailableFilename(input,ignore='junk')
            print(result)
            self.assertEqual(str(result), expected)

    def test_find(self)->None:
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
            actual=[str(x.path) for x in actual]
            print(actual)
            print()
            self.assertEqual(len(actual), len(t[0]))
            for item in t[0]:
                self.assertIn(str(FilePath(item).absolute()), actual)

    def test_createShortcut(self)->None:
        """
        Test creating shortcuts without overwriting existing ones
        """
        print()
        f='targetFile.txt'
        shutil.copy2(str(__HERE__/f),str(results_dir/f))
        print('creating new shortcut')
        lnk=createLink(results_dir/f,linkType=LINKTYPE_SHORTCUT)
        assert lnk is not None
        print('   ',lnk.path)
        print('   - points to -')
        print('   ',lnk.targetPath)
        self.assertEqual(str(results_dir / f) + '.lnk', str(lnk.path))
        self.assertEqual(str(lnk.targetPath), str(results_dir / f))
        print('Now make sure it doesn\'t overwrite')
        lnk2=createLink(results_dir/f,linkType=LINKTYPE_SHORTCUT)
        if lnk2 is None:
            self.fail('createLink returned None')
            return
        self.assertEqual(str(results_dir / f) + ' 1.lnk', str(lnk2.path))
        self.assertEqual(str(lnk2.targetPath), str(results_dir / f))

    def test_iconLoader(self)->None:
        """
        Test loading icons from files and file types
        """
        print()
        actual=iconImage(__HERE__/'defaulticon.ico')
        print('SHELL32.dll:0')
        self.assertTrue(compareImage(actual, iconImage('SHELL32.dll:0')))
        print(':0')
        self.assertTrue(compareImage(actual, iconImage(':0')))
        print('""')
        self.assertTrue(compareImage(actual, iconImage('')))
        print(':1')
        self.assertTrue(compareImage(
            actual, iconImage(':1', index_plus_one=False)))
        print('someMissingExtension')
        ico=iconForFiletype('x.someMissingExtension')
        ico.save('bogus.ico')
        # test error conditions
        try:
            iconImage('missing.dll')
            self.fail('missing icon did not raise FileNotFoundError')
        except FileNotFoundError:
            pass
        try:
            iconImage('./missing.dll')
            self.fail('missing icon did not raise FileNotFoundError')
        except FileNotFoundError:
            pass

def suite(
    tests:typing.Optional[typing.Iterable[str]]=None
    )->unittest.TestSuite:
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
    #testSuite.addTest(Test("test_toFolderShortcut"))
    testSuite.addTest(Test("test_fromFolderShortcut"))
    #testSuite.addTest(Test("iconLoader"))
    return testSuite


def run(
    tests: Optional[Sequence[str]] = None,
    output: Optional[str] = None,
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
        runner = unittest.TextTestRunner(
            sys.stdout, verbosity=verbosity, failfast=failfast)
        runner.run(suite(tests))
        return
    with open(output, 'w', encoding='utf-8') as stream:
        runner = unittest.TextTestRunner(
            stream, verbosity=verbosity, failfast=failfast)
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
    cmdline(sys.argv[1:])

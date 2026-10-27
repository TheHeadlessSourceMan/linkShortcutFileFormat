# This is the setup info for the python installer.
# You probably don't need to do anything with it directly.
# Just run make and it will be used to create a distributable package
# for more info on how this works, see:
#    http://wheel.readthedocs.org/en/latest/
#    and/or
#    http://pythonwheels.com
from setuptools import setup, Distribution


class BinaryDistribution(Distribution):
    def is_pure(self):
        return True # return False if there is OS-specific files


def cmdline(args):
    """
    Run the command line

    :param args: command line arguments (WITHOUT the filename)
    """
    import os
    here=os.path.dirname(os.path.realpath( __file__ ))
    name='linkShortcut'
    version='1.0'
    description='A tool for creating and managing shell links/shortcuts.'
    packages=[name]
    package_data={ # add all files for a package
        name:[]
    }
    package_dir={name:here}
    distclass=BinaryDistribution
    setup(name=name,version=version,description=description,packages=packages,package_dir=package_dir,package_data=package_data,distclass=distclass)


if __name__=='__main__':
    import sys
    cmdline(sys.argv[1:])

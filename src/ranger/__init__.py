# This file is part of ranger, the console file manager.
# License: GNU GPL version 3, see the file "AUTHORS" for details.

"""A console file manager with VI key bindings.

It provides a minimalistic and nice curses interface with a view on the
directory hierarchy.  The secondary task of ranger is to figure out which
program you want to use to open your files with.
"""
import os


# Version helper
def version_helper():
    if __release__:
        version_string = f'ranger {__version__}'
    else:
        import subprocess
        try:
            with subprocess.Popen( ["git", "describe"], universal_newlines=True, cwd=RANGERDIR, stdout=subprocess.PIPE, stderr=subprocess.PIPE ) as git_describe:
                (git_description, _) = git_describe.communicate()
            version_string = f'ranger-master {git_description.strip('\n')}'
        except (OSError, subprocess.CalledProcessError, AttributeError):
            version_string = f'ranger-master {__version__}+dev'
    return version_string


# Information
__license__ = 'GPL3'
__version__ = '1.9.3'
__release__ = False
__author__ = __maintainer__ = 'Roman Zimbelmann'
__email__ = 'hut@hut.pm'

# Constants
RANGERDIR = os.path.dirname(__file__)
TICKS_BEFORE_COLLECTING_GARBAGE = 100
TIME_BEFORE_FILE_BECOMES_GARBAGE = 1200
MAX_RESTORABLE_TABS = 3
MACRO_DELIMITER = '%'
MACRO_DELIMITER_ESC = '%%'
DEFAULT_PAGER = 'less'
USAGE = '%prog [options] [path]'
VERSION = version_helper()

# These variables are ignored if the corresponding
# XDG environment variable is non-empty and absolute
CACHEDIR = os.path.expanduser('~/.cache/ranger')
CONFDIR = os.path.expanduser('~/.config/ranger')
DATADIR = os.path.expanduser('~/.local/share/ranger')

args = None  # pylint: disable=invalid-name

# This file is part of ranger, the console file manager.
# License: GNU GPL version 3, see the file "AUTHORS" for details.
import shutil


def which(cmd):
    return shutil.which(cmd)

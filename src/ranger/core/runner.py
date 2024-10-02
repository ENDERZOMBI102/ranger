# This file is part of ranger, the console file manager.
# License: GNU GPL version 3, see the file "AUTHORS" for details.

"""This module is an abstract layer over subprocess.Popen

It gives you highlevel control about how processes are run.

Example:
run = Runner(logfunc=print)
run('sleep 2', wait=True)         # waits until the process exists
run(['ls', '--help'], flags='p')  # pipes output to pager
run()                             # prints an error message

List of allowed flags:
s: silent mode. output will be discarded.
f: fork the process.
p: redirect output to the pager.
c: run only the current file (not handled here).
w: wait for enter-press afterward.
r: run application with root privilege (requires sudo or doas).
t: run application in a new terminal window.
(An uppercase key negates the respective lower case flag)
"""
import logging
import os
import sys
import io
import subprocess
import typing

import ranger.ext.get_executables
import ranger.ext.popen_forked
import ranger.container.file
import ranger.core.fm
import ranger.gui.ui


LOG = logging.getLogger(__name__)


# TODO: Remove unused parts of runner.py
# ALLOWED_FLAGS = 'sdpwcrtSDPWCRT'
ALLOWED_FLAGS = 'cfrtCFRT'


class Context:
    """A context object contains data on how to run a process.

    The attributes are:
    action -- a string with a command or a list of arguments for
        the Popen call.
    app -- the name of the app function. ("vim" for app_vim.)
        app is used to get an action if the user didn't specify one.
    mode -- a number, mainly used in determining the action in app_xyz()
    flags -- a string with flags which change the way programs are run
    files -- a list containing files, mainly used in app_xyz
    file -- an arbitrary file from that list (or None)
    fm -- the filemanager instance
    wait -- boolean, wait for the end or execute programs in parallel?
    popen_kws -- keyword arguments which are directly passed to Popen
    """
    action: str
    app: str
    mode: int
    flags: str
    files: list[ranger.container.file.File]
    file: ranger.container.file.File | None
    fm: 'ranger.core.fm.FM'
    wait: bool
    popen_kws: dict[str, object]

    def __init__(self, action: str = None, app: str = None, mode: int = None, flags: str = None, files: list[ranger.container.file.File] = None, file=None, fm=None, wait=None, popen_kws=None):
        self.action = action
        self.app = app
        self.mode = mode
        self.flags = flags
        self.files = files
        self.file = file
        self.fm = fm
        self.wait = wait
        self.popen_kws = popen_kws

    @property
    def filepaths(self):
        try:
            return [ f.path for f in self.files ]
        except AttributeError:
            return []

    def __iter__(self):
        """Iterate over file paths"""
        yield from self.filepaths

    def squash_flags(self):
        """Remove duplicates and lowercase counterparts of uppercase flags"""
        for flag in self.flags:
            if ord(flag) <= 90:
                bad = flag + flag.lower()
                self.flags = ''.join(c for c in self.flags if c not in bad)


class Runner:
    ui: ranger.gui.ui.UI | None
    fm: typing.Union['ranger.core.fm.FM', None]
    logfunc: typing.Callable[[str], None] | None
    zombies: set[ subprocess.Popen ]

    def __init__(self, ui: ranger.gui.ui.UI = None, logfunc: typing.Callable[[str], None] = None, fm: 'ranger.core.fm.FM' = None):
        self.ui = ui
        self.fm = fm
        self.logfunc = logfunc
        self.zombies = set()

    def _log(self, text: str) -> bool:
        try:
            self.logfunc(text)
        except TypeError:
            pass
        return False

    def _activate_ui( self, value: bool ) -> None:
        if self.ui is None:
            return
        if value:
            try:
                self.ui.initialize()
            except Exception as ex:
                self._log("Failed to initialize UI")
                LOG.exception(ex)
        else:
            try:
                self.ui.suspend()
            except Exception as ex:
                self._log("Failed to suspend UI")
                LOG.exception(ex)

    def __call__( self, action=None, try_app_first=False, app='default', files=None, mode=0, flags='', wait=True, **popen_kws ):
        """Run the application in the way specified by the options.

        Returns False if nothing can be done, None if there was an error,
        otherwise the process object returned by Popen().

        This function tries to find an action if none is defined.
        """

        # Find an action if none was supplied by
        # creating a Context object and passing it to
        # an Application object.

        context = Context(app=app, files=files, mode=mode, fm=self.fm, flags=flags, wait=wait, popen_kws=popen_kws, file=files and files[0] or None)

        if action is None:
            return self._log("No way of determining the action!")

        # Preconditions

        context.squash_flags()
        popen_kws = context.popen_kws  # shortcut

        toggle_ui = True
        pipe_output = False
        wait_for_enter = False

        # check if the command might need a shell to run
        if 'shell' not in popen_kws:
            popen_kws['shell'] = isinstance(action, str)

        # Set default shell for Popen
        if popen_kws['shell']:
            popen_kws['executable'] = os.environ['SHELL']

        if 'stdout' not in popen_kws:
            popen_kws['stdout'] = sys.stdout
        if 'stderr' not in popen_kws:
            popen_kws['stderr'] = sys.stderr

        # Evaluate the flags to determine keywords for Popen() and other variables
        if 'p' in context.flags:  # redirect output to the pager.
            popen_kws['stdout'] = subprocess.PIPE
            popen_kws['stderr'] = subprocess.STDOUT
            toggle_ui = False
            pipe_output = True
            context.wait = False
        if 's' in context.flags:  # silent mode. output will be discarded.
            # Using a with-statement for these is inconvenient.
            devnull_writable = io.open(os.devnull, 'w', encoding="utf-8")
            devnull_readable = io.open(os.devnull, 'r', encoding="utf-8")
            popen_kws['stdout'] = devnull_writable
            popen_kws['stderr'] = devnull_writable
            popen_kws['stdin'] = devnull_readable
            toggle_ui = False
        if 'f' in context.flags:  # fork the process.
            toggle_ui = False
            context.wait = False
        if 'w' in context.flags:  # wait for enter-press afterward.
            if not pipe_output and context.wait:  # <-- sanity check
                wait_for_enter = True
        if 'r' in context.flags:  # run application with root privilege (requires sudo).
            # TODO: make 'r' flag work with pipes
            if 'sudo' not in ranger.ext.get_executables.get_executables():
                return self._log("Can not run with 'r' flag, sudo is not installed!")
            f_flag = 'f' in context.flags
            if isinstance(action, str):
                action = 'sudo ' + (f_flag and '-b ' or '') + action
            else:
                action = ['sudo'] + (f_flag and ['-b'] or []) + action
            toggle_ui = True
            context.wait = True
        if 't' in context.flags:  # run application in a new terminal window.
            if not ('WAYLAND_DISPLAY' in os.environ or sys.platform == 'darwin' or 'DISPLAY' in os.environ):
                return self._log("Can not run with 't' flag, no display found!")
            term = ranger.ext.get_executables.get_term()
            if isinstance(action, str):
                action = term + ' -e ' + action
            else:
                action = [term, '-e'] + action
            toggle_ui = False
            context.wait = False

        popen_kws['args'] = action

        # Finally, run it
        if toggle_ui:
            self._activate_ui(False)

        error: Exception | None = None
        process: subprocess.Popen | None = None

        try:
            self.fm.signal_emit('runner.execute.before', popen_kws=popen_kws, context=context)
            try:
                if 'f' in context.flags and 'r' not in context.flags:
                    # This can fail and return False if os.fork() is not
                    # supported, but we assume it is, since curses is used.
                    ranger.ext.popen_forked.Popen_forked(**popen_kws)
                else:
                    process = subprocess.Popen(**popen_kws)
            except OSError as ex:
                error = ex
                self._log( f"Failed to run: {action}\n{ex}" )
            else:
                if context.wait:
                    process.wait()
                elif process:
                    self.zombies.add(process)
                if wait_for_enter:
                    sys.stdout.write("Press ENTER to continue")
                    input()
        finally:
            self.fm.signal_emit('runner.execute.after', popen_kws=popen_kws, context=context, error=error)
            if toggle_ui:
                self._activate_ui(True)
            if pipe_output and process:
                return self(action='less', app='pager', try_app_first=True, stdin=process.stdout)
            return process  # pylint: disable=lost-exception

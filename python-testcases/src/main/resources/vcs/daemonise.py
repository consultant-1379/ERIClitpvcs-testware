# Cheap and hacky daemonizer. This does not prevent against race conditions
# and the like
import os
import sys
import atexit
import time
from signal import SIGTERM


class Daemonizer(object):

    def __init__(self, fn,
                 pidfile='/var/run/daemoniser',
                 stdin='/dev/null',
                 stdout='/dev/null',
                 stderr='/dev/null'):
        self._fn = fn
        self._pidfile = pidfile
        self._stdin = stdin
        self._stdout = stdout
        self._stderr = stderr

    def _fork_out(self, fork_no):
        try:
            pid = os.fork()
            if pid > 0:
                # Exit first parent
                return True
            # False to mean we're the forked process
            return False
        except OSError, e:
            sys.stderr.write("%s fork failed: %d (%s)\n" %
                                (fork_no, e.errno, e.strerror))
            sys.exit(1)

    def _redirect_fds(self):
        for _stream in (sys.stdout, sys.stdin):
            _stream.flush()

        si = file(self._stdin, 'r')
        so = file(self._stdout, 'a+')
        se = file(self._stderr, 'a+', 0)

        for _fd, _stream in ((si, sys.stdin), (so, sys.stdout),
                             (se, sys.stderr)):
            os.dup2(_fd.fileno(), _stream.fileno())

    def _pre_daemonize(self):
        os.chdir("/")
        os.umask(0)
        os.setsid()

    def _daemonize(self):
        """
        Stolen from:
        https://web.archive.org/web/20160304012843/http://www.jejik.com/
        articles/2007/02/a_simple_unix_linux_daemon_in_python/
        """
        # Look, this is weird at first. What happens when you make a daemon 
        # is you create a child process that then creates another child 
        # process, but only after the first child does some stuff with 
        if self._fork_out("First"):
            # False to signify we're still the first pid
            return False
        self._pre_daemonize()

        if self._fork_out("Second"):
            # we're the middle pid, exit
            sys.exit(0)

        self._redirect_fds()

        atexit.register(self._delpid)
        self.writepid()
        self._fn()
        return True

    def _delpid(self):
        os.remove(self._pidfile)

    def writepid(self):
        pid = str(os.getpid())
        file(self._pidfile, 'w+').write("%s\n" % pid)

    def _getpid(self):
        pid = None
        try:
            pf = open(self._pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        return pid

    def start(self):
        if self._getpid():
            sys.stderr.write("Already started\n")
            return 0
        is_fork = self._daemonize()
        # Brain damage warning: the process that started running 
        # the start method is not the one that's calling the callback
        if is_fork:
            #self._fn()
            # Exit because we don't want to return to our caller
            sys.exit(0)

    def _cleanpidfile(self):
        try:
            self._delpid()
        except IOError:
            # Swallow the exception
            pass

    def _kill_pid(self, pid):
        try:
            while True:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError, err:
            err_str = str(err)
            if "No such process" in err_str:
                self._cleanpidfile()
                return
            raise err

    def stop(self):
        pid = self._getpid()
        if not pid:
            sys.stderr.write("Already stopped")
            return
        self._kill_pid(pid)

    def restart(self):
        self.stop()
        return self.start()

    def status(self):
        pid = self._getpid()
        if not pid:
            return 1
        # Pidfile exists, check actual process
        try:
            # send signal zero
            os.kill(pid, 0)
        except OSError, err:
            if "No such process" in str(err):
                self._cleanpidfile()
                return 1
            # We don't know what to do with it, raise it
            raise err
        return 0

    def get_cmds(self):
        return {"stop": self.stop,
                "start": self.start,
                "restart": self.restart,
                "status": self.status}

    def usage(self):
        sys.stderr.write("Please provide an action of either 'start', "
                         "'stop', 'status' or 'restart'.\n")
        return 1

    def perform_action(self, action=""):
        return (self.get_cmds().get(action, self.usage)())

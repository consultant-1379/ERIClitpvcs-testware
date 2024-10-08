#!/usr/bin/env python

import os
import os.path
import sys

# Basically want start/stop/status
PID_FILE = "/tmp/test-lsb-4"


def pidfile_exists():
    return os.path.exists(PID_FILE)


def create_pidfile():
    open(PID_FILE, "w").close()


def delete_pidfile():
    try:
        os.remove(PID_FILE)
    except:
        pass


def start():
    if pidfile_exists():
        # Exit early
        print "Already started"
        return 0
    create_pidfile()
    print "Started"
    return 0


def stop():
    if not pidfile_exists():
        print "Already stopped"
        return 1
    delete_pidfile()
    print "Stopped"
    return 0


def status():
    if pidfile_exists():
        print "OK"
        return 0
    print "NOK"
    return 1


def help(cmd="test-lsb-04.py"):
    doc = """
    Mock LSB, supported commands
    start
    stop
    status
    """
    print doc


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('start', 'stop', 'status'):
        help()
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "start":
        sys.exit(start())
    elif cmd == "stop":
        sys.exit(stop())
    else:
        sys.exit(status())


if __name__ == "__main__":
    main()

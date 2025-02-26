#!/usr/bin/env python3

import subprocess
import numbers
import threading
import pwd
import socket
import re
import os
from os.path import exists
from aptsources.sourceslist import SourcesList


def shell_exec_popen(command, kwargs=None):
    """ Execute a command with Popen (returns the returncode attribute) """
    if not kwargs:
        kwargs = {}
    print((f"Executing: {command}"))
    # return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, **kwargs)
    return subprocess.Popen(command,
                            shell=True,
                            bufsize=0,
                            stdout=subprocess.PIPE,
                            universal_newlines=True,
                            **kwargs)


def shell_exec(command, wait=False):
    """ Execute a command (returns the returncode attribute) """
    print((f"Executing: {command}"))
    if wait:
        return subprocess.check_call(command, shell=True)
    return subprocess.call(command, shell=True)


def getoutput(command, timeout=None):
    """ Return command output (list) """
    try:
        output = subprocess.check_output(
            command, shell=True, timeout=timeout).decode('utf-8').strip().split('\n')
    except Exception as detail:
        print((f'getoutput exception: {detail}'))
        output = ['']
    return output


def chroot_exec(command, target):
    """ Excecute command in chroot """
    command = command.replace('"', "'").strip()  # FIXME
    return shell_exec(f'chroot {target}/ /bin/sh -c "{command}"')


def get_repo_suite(pattern):
    """Return repo suite by pattern
       Used in scripts/*

    Args:
        pattern (str): regexp pattern to match suite

    Returns:
        str: repo suite
    """
    sources_list = SourcesList().list
    for source_entry in sources_list:
        # Save suites and types separately because of Deb822SourceEntry/SourceEntry differences
        try:
            suites = source_entry.suites
        except AttributeError:
            suites = [source_entry.dist]
        if not source_entry.disabled:
            for suite in suites:
                match = re.search(pattern=pattern, string=suite, flags=re.IGNORECASE)
                if match:
                    return suite
    return ''


# Convert string to number
def str_to_nr(value):
    """ Convert string to number """
    if isinstance(value, numbers.Number):
        # Already numeric
        return value

    number = None
    try:
        number = int(value)
    except ValueError:
        try:
            number = float(value)
        except ValueError:
            number = None
    return number


def is_numeric(value):
    """ Check if value is a number """
    return bool(str_to_nr(value))


# Get Debian's version number (float)
def get_debian_version():
    """ Get Debian's version number (float) """
    version = 0
    if exists('/etc/debian_version'):
        cmd = "grep -oP '^[a-z0-9]+' /etc/debian_version"
        version = str_to_nr(getoutput(cmd)[0].strip())
    if not version:
        cmd = "grep -Ei 'version=|version_id=|release=' /etc/*release | grep -oP '[0-9]+'"
        versions = getoutput(cmd)
        for version in versions:
            if is_numeric(version):
                version = str_to_nr(version)
                break
    return version


# Check for internet connection
def has_internet_connection(hostname=None):
    """ Check for internet connection """
    # Taken from https://stackoverflow.com/questions/20913411/test-if-an-internet-connection-is-present-in-python
    if not hostname:
        hostname = 'solydxk.com'
    try:
        # See if we can resolve the host name - tells us if there is
        # A DNS listening
        host = socket.gethostbyname(hostname)
        # Connect to the host - tells us if the host is actually reachable
        s = socket.create_connection((host, 80), 2)
        s.close()
        return True
    except Exception:
        pass # We ignore any errors, returning False
    return False


def is_running_live():
    """ Is the system a live system """
    live_dirs = ['/live', '/lib/live/mount', '/rofs']
    for live_dir in live_dirs:
        if exists(live_dir):
            return True
    return False


def in_virtual_box():
    """ Check if running in virtual box """
    virtual_box = 'VirtualBox'
    dmi_bios_version = getoutput(
        f"grep '{virtual_box}' /sys/devices/virtual/dmi/id/bios_version")
    dmi_system_product = getoutput(
        f"grep '{virtual_box}' /sys/devices/virtual/dmi/id/product_name")
    dmi_board_product = getoutput(
        f"grep '{virtual_box}' /sys/devices/virtual/dmi/id/board_name")
    if virtual_box not in dmi_bios_version and \
       virtual_box not in dmi_system_product and \
       virtual_box not in dmi_board_product:
        return False
    return True


def get_logged_user():
    """ Get user name """
    p = os.popen("logname", 'r')
    user_name = p.readline().strip()
    p.close()
    if user_name == "":
        user_name = pwd.getpwuid(os.getuid()).pw_name
    return user_name


# Class to run commands in a thread and return the output in a queue
class ExecuteThreadedCommands(threading.Thread):

    def __init__(self, commandList, theQueue=None, returnOutput=False):
        super(ExecuteThreadedCommands, self).__init__()
        self.commands = commandList
        self.queue = theQueue
        self.returnOutput = returnOutput

    def run(self):
        if isinstance(self.commands, (list, tuple)):
            for cmd in self.commands:
                self.exec_cmd(cmd)
        else:
            self.exec_cmd(self.commands)

    def exec_cmd(self, cmd):
        if self.returnOutput:
            ret = getoutput(cmd)
        else:
            ret = shell_exec(cmd)
        if self.queue is not None:
            self.queue.put(ret)

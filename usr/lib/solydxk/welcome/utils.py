#!/usr/bin/env python3

import subprocess
from socket import timeout
from urllib.request import ProxyHandler, HTTPBasicAuthHandler, Request, \
                           build_opener, HTTPHandler, install_opener, urlopen
from urllib.error import URLError, HTTPError
from random import choice
import re
import threading
import os
from os.path import exists
import pwd
import apt


def shell_exec_popen(command, kwargs={}):
    print(('Executing:', command))
    return subprocess.Popen(command, shell=True,
                            stdout=subprocess.PIPE, **kwargs)


def shell_exec(command):
    print(('Executing:', command))
    return subprocess.call(command, shell=True)


def getoutput(command):
    #return shell_exec(command).stdout.read().strip()
    try:
        output = subprocess.check_output(command, shell=True).decode('utf-8').strip().split('\n')
    except:
        output = []
    return output


def chroot_exec(command):
    command = command.replace('"', "'").strip()  # FIXME
    return shell_exec('chroot /target/ /bin/sh -c "%s"' % command)


def memoize(func):
    """ Caches expensive function calls.

    Use as:

        c = Cache(lambda arg: function_to_call_if_yet_uncached(arg))
        c('some_arg')  # returns evaluated result
        c('some_arg')  # returns *same* (non-evaluated) result

    or as a decorator:

        @memoize
        def some_expensive_function(args [, ...]):
            [...]

    See also: http://en.wikipedia.org/wiki/Memoization
    """
    class memodict(dict):
        def __call__(self, *args):
            return self[args]

        def __missing__(self, key):
            ret = self[key] = func(*key)
            return ret
    return memodict()


# Convert string to number
def str_to_nr(stringnr, toInt=False):
    nr = 0
    # Might be a int or float: convert to str
    stringnr = str(stringnr).strip()
    try:
        if toInt:
            nr = int(stringnr)
        else:
            nr = float(stringnr)
    except ValueError:
        nr = 0
    return nr


# Get Debian's version number (float)
def get_debian_version():
    try:
        version = str_to_nr(getoutput("grep -oP '^[0-9]+' /etc/debian_version")[0], True)
    except:
        try:
            version = str_to_nr(getoutput("grep VERSION= /etc/os-release | grep -oP '[0-9]+'")[0], True)
        except:
            version = str_to_nr(getoutput("grep DISTRIB_RELEASE= /etc/lsb-release | grep -oP '[0-9]+'")[0], True)
    return version


def get_config_dict(file, key_value=re.compile(r'^\s*(\w+)\s*=\s*["\']?(.*?)["\']?\s*(#.*)?$')):
    """Returns POSIX config file (key=value, no sections) as dict.
    Assumptions: no multiline values, no value contains '#'. """
    d = {}
    with open(file) as f:
        for line in f:
            try:
                key, value, _ = key_value.match(line).groups()
            except AttributeError:
                continue
            d[key] = value
    return d


# Check for internet connection
def has_internet_connection(test_url=None):
    urls = []
    if test_url is not None:
        urls.append(test_url)
    if not urls:
        src_lst = '/etc/apt/sources.list'
        if exists(src_lst):
            with open(src_lst, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith('#'):
                        matchObj = re.search(r'http[s]{,1}://[a-z0-9\.]+', line)
                        if matchObj:
                            urls.append(matchObj.group(0))
    for url in urls:
        if get_value_from_url(url) is not None:
            return True
    return False


def get_value_from_url(url, timeout_secs=5, return_errors=False):
    try:
        # http://www.webuseragents.com/my-user-agent
        user_agents = [
            'Mozilla/5.0 (X11; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.87 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'
        ]

        # Create proxy handler
        proxy = ProxyHandler({})
        auth = HTTPBasicAuthHandler()
        opener = build_opener(proxy, auth, HTTPHandler)
        install_opener(opener)

        # Create a request object with given url
        req = Request(url)

        # Get a random user agent and add that to the request object
        ua = choice(user_agents)
        req.add_header('User-Agent', ua)

        # Get the output of the URL
        output = urlopen(req, timeout=timeout_secs)

        # Decode to text
        txt = output.read().decode('utf-8')
        
        # Return the text
        return txt
        
    except (HTTPError, URLError) as error:
        err = 'ERROR: could not connect to {}: {}'.format(url, error)
        if return_errors:
            return err
        else:
            print((err))
            return None
    except timeout:
        err = 'ERROR: socket timeout on: {}'.format(url)
        if return_errors:
            return err
        else:
            print((err))
            return None


# Check if running in VB
def in_virtualbox():
    vb = 'VirtualBox'
    dmiBIOSVersion = getoutput("grep '{}' /sys/devices/virtual/dmi/id/bios_version".format(vb))
    dmiSystemProduct = getoutput("grep '{}' /sys/devices/virtual/dmi/id/product_name".format(vb))
    dmiBoardProduct = getoutput("grep '{}' /sys/devices/virtual/dmi/id/board_name".format(vb))
    if vb not in dmiBIOSVersion and \
       vb not in dmiSystemProduct and \
       vb not in dmiBoardProduct:
        return False
    return True


# Get the kernel's architecture
def get_architecture():
    arch = getoutput("uname -m")
    if arch:
        return arch[0]
    return ''


# Get the login name of the current user
def getUserLoginName():
    p = os.popen("logname", 'r')
    userName = p.readline().strip()
    p.close()
    if userName == "":
        userName = pwd.getpwuid(os.getuid()).pw_name
    return userName


# Check if a package is installed
def isPackageInstalled(packageName, alsoCheckVersion=True):
    isInstalled = False
    try:
        cmd = 'dpkg-query -l %s | grep ^i' % packageName
        if '*' in packageName:
            cmd = 'aptitude search -w 150 %s | grep ^i' % packageName
        pckList = getoutput(cmd)
        for line in pckList:
            matchObj = re.search(r'([a-z]+)\s+([a-z0-9\-_\.]*)', line)
            if matchObj:
                if matchObj.group(1)[:1] == 'i':
                    if alsoCheckVersion:
                        cache = apt.Cache()
                        pkg = cache[matchObj.group(2)]
                        if pkg.installed.version == pkg.candidate.version:
                            isInstalled = True
                            break
                    else:
                        isInstalled = True
                        break
            if isInstalled:
                break
    except:
        pass
    return isInstalled


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

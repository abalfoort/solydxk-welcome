#!/usr/bin/env python3 -OO

import sys
import traceback
import os
import getopt
from welcome import SolydXKWelcome
from utils import get_logged_user, is_running_live
from dialogs import ErrorDialog, MessageDialog

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
_ = gettext.translation('solydxk-welcome', fallback=True).gettext

# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

# Handle arguments
try:
    opts, opt_args = getopt.getopt(sys.argv[1:], 'af', ['autostart', 'force'])
except getopt.GetoptError:
    sys.exit(2)

FORCE = False
AUTOSTART = False
LIVE = is_running_live()
OEM = get_logged_user()[-4:] == "-oem"

for opt, arg in opts:
    #print((">> opt = {} / opt_arg = {}".format(opt, opt_arg)))
    if opt in ('-a', '--autostart'):
        AUTOSTART = True
    elif opt in ('-f', '--force'):
        FORCE = True


# Set variables
scriptDir = os.path.dirname(os.path.realpath(__file__))
flagPath = os.path.join(os.environ.get('HOME'), '.sws.flag')

# Check if we can start
if AUTOSTART:
    if os.path.isfile(flagPath) or OEM or LIVE:
        sys.exit()

# Do not run in live environment
if LIVE and not FORCE:
    live_title = _("SolydXK Welcome")
    live_msg = _("SolydXK Welcome cannot be started in a live environment\n"
            "You can use the --force argument to start SolydXK Welcome in a live environment")
    MessageDialog(live_title, live_msg)
    sys.exit()

def uncaught_excepthook(*args):
    sys.__excepthook__(*args)
    if not __debug__:
        details = '\n'.join(traceback.format_exception(*args)).replace('<', '').replace('>', '')
        title = _('Unexpected error')
        msg = _('SolydXK Welcome has failed with the following unexpected error. '
                'Please submit a bug report!')
        ErrorDialog(title, f"<b>{msg}</b>", f"<tt>{details}</tt>", None, True, 'solydxk')

    sys.exit(1)

sys.excepthook = uncaught_excepthook

# main entry
if __name__ == "__main__":
    # Create an instance of our GTK application
    try:
        SolydXKWelcome()
        Gtk.main()
    except KeyboardInterrupt:
        pass

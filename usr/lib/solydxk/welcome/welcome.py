#!/usr/bin/env python3

# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')

# from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk, GLib
from gi.repository import Gtk, Gdk, GLib
from os.path import join, abspath, dirname, basename, exists, isdir
from utils import ExecuteThreadedCommands, has_internet_connection, \
                  getoutput, in_virtualbox, get_debian_version
from simplebrowser import SimpleBrowser
import os
from dialogs import ErrorDialog, WarningDialog, \
                    MessageDialog, QuestionDialog
from queue import Queue

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
_ = gettext.translation('solydxk-welcome', fallback=True).gettext


#class for the main window
class SolydXKWelcome(object):

    def __init__(self):

        # Check debian version
        self.deb_version = get_debian_version()

        # Check for backports
        self.isBackportsEnabled = bool(getoutput("grep backports /etc/apt/sources.list /etc/apt/sources.list.d/*.list | grep -v ^#"))

        # ================================
        # Define html page array [action (see below), script_name, (optional) post_exec]
        # 0 = no action (just show)
        # 1 = apt install
        # 2 = open external application
        self.pages = []
        self.pages.append([0, 'welcome'])
        if self.need_drivers():
            self.pages.append([2, 'drivers'])
        if self.isBackportsEnabled:
            self.pages.append([1, 'libreofficebp'])
        else:
            self.pages.append([1, 'libreoffice'])
        self.pages.append([1, 'business'])
        self.pages.append([1, 'multimedia'])
        self.pages.append([1, 'system'])
        self.pages.append([1, 'games'])
        self.pages.append([1, 'wine'])
        # ================================

        # Load window and widgets
        self.scriptName = basename(__file__)
        self.scriptDir = abspath(dirname(__file__))
        self.mediaDir = abspath(join(self.scriptDir, '../../../share/solydxk/welcome'))
        self.htmlDir = join(self.mediaDir, "html")
        self.builder = Gtk.Builder()
        self.builder.add_from_file(join(self.mediaDir, 'welcome.glade'))

        # Main window objects
        go = self.builder.get_object
        self.window = go("welcomeWindow")
        self.swWelcome = go("swWelcome")
        self.btnInstall = go("btnInstall")
        self.btnQuit = go("btnQuit")
        self.btnNext = go("btnNext")
        self.btnPrevious = go("btnPrevious")
        self.pbWelcome = go("pbWelcome")

        self.window.set_title("SolydXK Welcome")
        self.btnInstall.set_label(_("Install"))
        self.btnQuit.set_label(_("Quit"))
        self.btnNext.set_label(_("Next"))
        self.btnPrevious.set_label(_("Previous"))

        self.btnInstall.set_sensitive(False)
        self.btnPrevious.set_sensitive(False)

        # Resize the window to 75% of the screen size in the primary monitor
        display = Gdk.Display.get_default()
        pm = display.get_primary_monitor()
        geo = pm.get_geometry()
        w = geo.width
        h = geo.height
        if w > 640:
            self.window.set_default_size(w * 0.75, h * 0.75)
        else:
            self.window.fullscreen()

        # Initiate variables
        self.browser = SimpleBrowser()
        self.js_finished_action = []
        self.browser.connect("js-finished", self._js_finished)
        self.langDir = self.get_language_dir()
        self.selected_packages = []
        self.queue = Queue(-1)
        self.threads = {}
        self.currentPage = 0
        self.flagPath = os.path.join(os.environ.get('HOME'), '.sws.flag')
        self.lastPage = len(self.pages) - 1
        self.pbSavedState = 0
        self.nextSavedState = True
        self.prevSavedState = True
        self.cur_browser = None

        # Load first HTML page and show in window
        self.load_html(self.pages[0][1])
        self.swWelcome.add(self.browser)

        # Connect builder signals and show window
        self.builder.connect_signals(self)
        self.window.show_all()

    # ===============================================
    # Main window functions
    # ===============================================

    def install_packages(self, cur_browser):
        values = cur_browser.js_values
        # Do not install VirtualBox in VirtualBox client
        if in_virtualbox() and 'virtualbox' in values:
            msg = _("VirtualBox cannot be installed in a VirtualBox client.\n"
                    "This package is skipped.")
            MessageDialog(self.btnInstall.get_label(), msg)
            values.remove('virtualbox')

        # Install selected packages
        if values:
            page = self.pages[self.js_finished_action[1]][1]
            script = join(self.scriptDir, "scripts/{}".format(page))
            print(("Install packages ({}): {}".format(script, ' '.join(values))))
            self.exec_command("pkexec env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY {} {}".format(script, ' '.join(values)))
            if len(self.pages[self.currentPage]) == 3:
                post_exec = self.pages[self.currentPage][2]
                if post_exec:
                    #print(("    post_exec[0:4] = {}".format(post_exec[0:4])))
                    if post_exec[0:4] == 'http':
                        # load URL in window
                        self.browser.show_html(post_exec)
                    else:
                        # execute command
                        self.exec_command(post_exec)
        else:
            msg = _("Nothing to do:\n"
                    "No packages were selected.")
            MessageDialog(self.btnInstall.get_label(), msg)
            self.set_buttons_state(True)
    
    def _js_finished(self, cur_browser):
        # Save page object
        self.cur_browser = cur_browser
        
        if self.js_finished_action[0] == 'install':
            self.install_packages(self.cur_browser)
        else:
            # User switched page but selected packages to install
            if self.cur_browser.js_values:
                answer = QuestionDialog(self.btnInstall.get_label(),
                                      _("You selected some packages for installation.\n\n"
                                        "Do you want to install them now?\n"
                                        "Note: list is cleared if you continue without installing."))
                if answer:
                    # Install the package before switching to the next page
                    self.install_packages(self.cur_browser)

    def on_btnInstall_clicked(self, widget):
        actionNr = self.pages[self.currentPage][0]
        if actionNr > 0:
            # Check if there is an internet connection
            if not has_internet_connection():
                title = _("No internet connection")
                msg = _("You need an internet connection to install the additional software.\n"
                        "Please, connect to the internet and try again.")
                WarningDialog(title, msg)
                return

            # Disable buttons
            self.set_buttons_state(False)

            # Check for installation script
            page = self.pages[self.currentPage][1]
            script = join(self.scriptDir, "scripts/{}".format(page))
            if exists(script):
                if actionNr == 1:
                    # Set action to take
                    self.js_finished_action = ['install', self.currentPage]
                    # Get the values of the selected checkboxes
                    self.browser.get_element_values('package')
                    # Asynchronous handling: installation by callback function _js_finished
                elif actionNr == 2:
                    os.system("/bin/sh -c \"{}\" &".format(script))
                    self.set_buttons_state(True)
            else:
                msg = _("Cannot install the requested software:\n"
                        "Script not found: {}".format(script))
                ErrorDialog(self.btnInstall.get_label(), msg)
                self.set_buttons_state(True)

    def on_btnQuit_clicked(self, widget):
        self.on_welcomeWindow_destroy(widget)

    def on_btnPrevious_clicked(self, widget):
        self.switch_page(-1)

    def on_btnNext_clicked(self, widget):
        self.switch_page(1)

    def switch_page(self, count):
        # Set action to take
        self.js_finished_action = ['switch', self.currentPage]
        # Get the values of the selected checkboxes
        self.browser.get_element_values('package')
        
        # Switch page
        self.currentPage += count
        self.btnInstall.set_sensitive(self.pages[self.currentPage][0])
        self.btnPrevious.set_sensitive(self.currentPage)
        self.btnNext.set_sensitive(self.currentPage - self.lastPage)
        self.load_html(self.pages[self.currentPage][1])
        if self.currentPage > 0:
            self.pbWelcome.set_fraction(1 / (self.lastPage / self.currentPage))
        else:
            self.pbWelcome.set_fraction(0)
        if not self.btnNext.get_sensitive():
            self.btnPrevious.grab_focus()
        elif not self.btnPrevious.get_sensitive():
            self.btnNext.grab_focus()

    def load_html(self, page):
        page_path = '{0}/{1}.html'.format(self.langDir, page)
        if not exists(page_path):
            page_path = '{0}/{1}.html'.format(join(self.htmlDir, 'en'), page)
        if exists(page_path):
            self.browser.show_html(page_path, False)

    def get_language_dir(self):
        # First test if full locale directory exists, e.g. html/pt_BR,
        # otherwise perhaps at least the language is there, e.g. html/pt
        # and if that doesn't work, try html/pt_PT
        lang = self.get_current_language()
        path = join(self.htmlDir, lang)
        if not isdir(path):
            base_lang = lang.split('_')[0].lower()
            path = join(self.htmlDir, base_lang)
            if not isdir(path):
                path = join(self.htmlDir, "{}_{}".format(base_lang, base_lang.upper()))
                if not isdir(path):
                    path = join(self.htmlDir, 'en')
        return path

    def get_current_language(self):
        lang = os.environ.get('LANG', 'US').split('.')[0]
        if lang == '':
            lang = 'en'
        return lang

    def show_message(self, cmdOutput, onlyOnError=False):
        try:
            msg = _("There was an error during the installation.\n"
                    "Please, run 'sudo apt-get -f install' in a terminal.\n"
                    "Visit our forum for support: https://forums.solydxk.com")
            if int(cmdOutput) != 255:
                if int(cmdOutput) > 0:
                    # There was an error
                    ErrorDialog(self.btnInstall.get_label(), msg)
                elif not onlyOnError:
                    msg = _("The software has been successfully installed.")
                    MessageDialog(self.btnInstall.get_label(), msg)
        except:
            MessageDialog(self.btnInstall.get_label(), cmdOutput)

    def exec_command(self, command):
        try:
            # Run the command in a separate thread
            print(("Run command: {}".format(command)))
            name = 'aptcmd'
            t = ExecuteThreadedCommands([command], self.queue)
            self.threads[name] = t
            t.daemon = True
            t.start()
            self.queue.join()
            GLib.timeout_add(250, self.check_thread, name)

        except Exception as detail:
            ErrorDialog(self.btnInstall.get_label(), detail)

    def set_buttons_state(self, enable):
        if not enable:
            # Get widgets current state
            self.nextSavedState = self.btnNext.get_sensitive()
            self.prevSavedState = self.btnPrevious.get_sensitive()
            self.pbSavedState = self.pbWelcome.get_fraction()

            # Disable buttons and pulse the progressbar
            self.btnInstall.set_sensitive(False)
            self.btnNext.set_sensitive(False)
            self.btnPrevious.set_sensitive(False)
        else:
            # Set widgets back to old state
            self.pbWelcome.set_fraction(self.pbSavedState)
            self.btnNext.set_sensitive(self.nextSavedState)
            self.btnPrevious.set_sensitive(self.prevSavedState)
            self.btnInstall.set_sensitive(True)

        #print((">>> ({0}) nextSavedState={1}, prevSavedState={2}, pbSavedState={3}".format(enable, self.nextSavedState, self.prevSavedState, self.pbSavedState)))

    def check_thread(self, name):
        if self.threads[name].is_alive():
            self.pbWelcome.pulse()
            if not self.queue.empty():
                ret = self.queue.get()
                print(("Queue returns: {}".format(ret)))
                self.queue.task_done()
                self.show_message(ret, True)
            return True

        # Thread is done
        #print(("++ Thread is done"))
        if not self.queue.empty():
            ret = self.queue.get()
            self.queue.task_done()
            self.show_message(ret)
        del self.threads[name]

        # Enable buttons
        self.set_buttons_state(True)
        # Reset js_finished_action
        self.js_finished_action = []
        # Uncheck all check boxes
        self.cur_browser.switch_checked_elements('package', False)

        return False

    # Check with ddm if we can install proprietary drivers
    def need_drivers(self):
        if exists('/usr/bin/ddm'):
            hw_list = ['amd', 'nvidia', 'broadcom', 'pae']
            for hw in hw_list:
                drivers = getoutput("ddm -i %s -s" % hw)
                if drivers[0]:
                    return True
        return False

    # Close the gui
    def on_welcomeWindow_destroy(self, widget):
        # Create flag file
        print(('touch {}'.format(self.flagPath)))
        os.system('touch {}'.format(self.flagPath))
        # Close the app
        Gtk.main_quit()

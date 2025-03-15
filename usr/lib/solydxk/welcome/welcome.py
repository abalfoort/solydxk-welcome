#!/usr/bin/env python3
""" Welcome script """

import os
from queue import Queue
from os.path import join, abspath, dirname, basename, exists, isdir
from utils import ExecuteThreadedCommands, has_internet_connection, \
                  getoutput, in_virtual_box, get_debian_version, \
                  get_repo_suite, get_screen_size
from simplebrowser import SimpleBrowser

from dialogs import error_dialog, warning_dialog, \
                    message_dialog, question_dialog

# i18n: http://docs.python.org/3/library/gettext.html
import gettext
_ = gettext.translation('solydxk-welcome', fallback=True).gettext

# Make sure the right Gtk version is loaded
import gi
gi.require_version('Gtk', '3.0')
# from gi.repository import Gtk, GdkPixbuf, GObject, Pango, Gdk, GLib
from gi.repository import Gtk, Gdk, GLib

#class for the main window
class SolydXKWelcome():
    """ Main Welcome Class """
    def __init__(self):

        # Check debian version
        self.deb_version = get_debian_version()

        # ================================
        # Define html page array [action (see below), script_name, (optional) post_exec]
        # 0 = no action (just show)
        # 1 = apt install
        # 2 = open external application
        self.pages = []
        self.pages.append([0, 'welcome'])
        if self.need_drivers():
            self.pages.append([2, 'drivers'])
        if get_repo_suite('backports'):
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
        self.script_name = basename(__file__)
        self.script_dir = abspath(dirname(__file__))
        self.media_dir = abspath(join(self.script_dir, '../../../share/solydxk/welcome'))
        self.html_dir = join(self.media_dir, "html")
        if not exists(self.html_dir):
            # Dev environment
            self.html_dir = abspath(join(self.script_dir, '../../../../po'))
        self.builder = Gtk.Builder()
        self.builder.add_from_file(join(self.media_dir, 'welcome.glade'))

        # Main window objects
        go = self.builder.get_object
        self.window = go("welcome_window")
        self.sw_welcome = go("sw_welcome")
        self.btn_install = go("btn_install")
        self.btn_quit = go("btn_quit")
        self.btn_next = go("btn_next")
        self.btn_previous = go("btn_previous")
        self.pb_welcome = go("pb_welcome")

        self.window.set_title("SolydXK Welcome")
        self.btn_install.set_label(_("Install"))
        self.btn_quit.set_label(_("Quit"))
        self.btn_next.set_label(_("Next"))
        self.btn_previous.set_label(_("Previous"))

        self.btn_install.set_sensitive(False)
        self.btn_previous.set_sensitive(False)

        # Resize the window to 75% of the screen size in the primary monitor
        mon_width, mon_height = get_screen_size()
        if mon_width > 640:
            self.window.set_default_size(mon_width * 0.75, mon_height * 0.75)
        else:
            self.window.fullscreen()

        # Initiate variables
        self.browser = SimpleBrowser()
        self.js_finished_action = []
        self.browser.connect("js-finished", self._js_finished)
        self.lang_dir = self.get_language_dir()
        self.selected_packages = []
        self.queue = Queue(-1)
        self.threads = {}
        self.current_page = 0
        self.flag_path = os.path.join(os.environ.get('HOME'), '.sws.flag')
        self.last_page = len(self.pages) - 1
        self.pb_saved_state = 0
        self.next_saved_state = True
        self.prev_saved_state = True
        self.cur_browser = None

        # Load first HTML page and show in window
        self.load_html(self.pages[0][1])
        self.sw_welcome.add(self.browser)

        # Connect builder signals and show window
        self.builder.connect_signals(self)
        self.window.show_all()

    # ===============================================
    # Main window functions
    # ===============================================

    def install_packages(self, cur_browser):
        """Install selected packages
           but prevent VB install in VB client

        Args:
            cur_browser (object): Set by _js_finished - browser page object
        """
        values = cur_browser.js_values
        # Do not install VirtualBox in VirtualBox client
        if in_virtual_box() and 'virtualbox' in values:
            msg = _("VirtualBox cannot be installed in a VirtualBox client.\n"
                    "This package is skipped.")
            message_dialog(self.btn_install.get_label(), msg)
            values.remove('virtualbox')

        # Install selected packages
        if values:
            page = self.pages[self.js_finished_action[1]][1]
            script = join(self.script_dir, f"scripts/{page}")
            print((f"Install packages ({script}): {' '.join(values)}"))
            self.exec_command("pkexec env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY" \
                              f" {script} {' '.join(values)}")
            if len(self.pages[self.current_page]) == 3:
                post_exec = self.pages[self.current_page][2]
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
            message_dialog(self.btn_install.get_label(), msg)
            self.set_buttons_state(True)

    def _js_finished(self, cur_browser):
        # Save page object
        self.cur_browser = cur_browser

        if self.js_finished_action[0] == 'install':
            self.install_packages(self.cur_browser)
        else:
            # User switched page but selected packages to install
            if self.cur_browser.js_values:
                answer = question_dialog(self.btn_install.get_label(),
                        _("You selected some packages for installation.\n\n"
                        "Do you want to install them now?\n"
                        "Note: list is cleared if you continue without installing."))
                if answer:
                    # Install the package before switching to the next page
                    self.install_packages(self.cur_browser)

    def on_btn_install_clicked(self, widget):
        """ Install button action """
        action_nr = self.pages[self.current_page][0]
        if action_nr > 0:
            # Check if there is an internet connection
            if not has_internet_connection():
                title = _("No internet connection")
                msg = _("You need an internet connection to install the additional software.\n"
                        "Please, connect to the internet and try again.")
                warning_dialog(title, msg)
                return

            # Disable buttons
            self.set_buttons_state(False)

            # Check for installation script
            page = self.pages[self.current_page][1]
            script = join(self.script_dir, f"scripts/{page}")
            if exists(script):
                if action_nr == 1:
                    # Set action to take
                    self.js_finished_action = ['install', self.current_page]
                    # Get the values of the selected checkboxes
                    self.browser.get_element_values('package')
                    # Asynchronous handling: installation by callback function _js_finished
                elif action_nr == 2:
                    os.system(f"/bin/sh -c \"{script}\" &")
                    self.set_buttons_state(True)
            else:
                msg = _("Cannot install the requested software:\n"
                        f"Script not found: {script}")
                error_dialog(self.btn_install.get_label(), msg)
                self.set_buttons_state(True)

    def on_btn_quit_clicked(self, widget):
        """ Button Quit action """
        self.on_welcome_window_destroy(widget)

    def on_btn_previous_clicked(self, widget):
        """ Button Previous action """
        self.switch_page(-1)

    def on_btn_next_clicked(self, widget):
        """ Button Previous action """
        self.switch_page(1)

    def switch_page(self, count):
        """ Switch browser page """
        # Set action to take
        self.js_finished_action = ['switch', self.current_page]
        # Get the values of the selected checkboxes
        self.browser.get_element_values('package')

        # Switch page
        self.current_page += count
        self.btn_install.set_sensitive(self.pages[self.current_page][0])
        self.btn_previous.set_sensitive(self.current_page)
        self.btn_next.set_sensitive(self.current_page - self.last_page)
        self.load_html(self.pages[self.current_page][1])
        if self.current_page > 0:
            self.pb_welcome.set_fraction(1 / (self.last_page / self.current_page))
        else:
            self.pb_welcome.set_fraction(0)
        if not self.btn_next.get_sensitive():
            self.btn_previous.grab_focus()
        elif not self.btn_previous.get_sensitive():
            self.btn_next.grab_focus()

    def load_html(self, page):
        """Load html into given page

        Args:
            page (object): browser page
        """
        page_path = f'{self.lang_dir}/{page}.html'
        if not exists(page_path):
            page_path = f"{join(self.html_dir, 'en')}/{page}.html"
        if exists(page_path):
            self.browser.show_html(page_path, False)

    def get_language_dir(self):
        """ Get the language directory """
        # First test if full locale directory exists, e.g. html/pt_BR,
        # otherwise perhaps at least the language is there, e.g. html/pt
        # and if that doesn't work, try html/pt_PT
        lang = self.get_current_language()
        path = join(self.html_dir, lang)
        if not isdir(path):
            base_lang = lang.split('_')[0].lower()
            path = join(self.html_dir, base_lang)
            if not isdir(path):
                path = join(self.html_dir, f"{base_lang}_{base_lang.upper()}")
                if not isdir(path):
                    path = join(self.html_dir, 'en')
        return path

    def get_current_language(self):
        """ Get current language """
        lang = os.environ.get('LANG', 'US').split('.')[0]
        if lang == '':
            lang = 'en'
        return lang

    def show_message(self, cmd_output, only_on_error=False):
        """Show a user message

        Args:
            cmd_output (str): output of the command
            only_on_error (bool, optional): only show when error. Defaults to False.
        """
        try:
            msg = _("There was an error during the installation.\n"
                    "Please, run 'sudo apt-get -f install' in a terminal.\n"
                    "Visit our forum for support: https://forums.solydxk.com")
            if int(cmd_output) != 255:
                if int(cmd_output) > 0:
                    if int(cmd_output) == 100:
                        msg = _("Could not get lock /var/lib/dpkg/lock\n"
                                "Is another process using it?")
                    # There was an error
                    error_dialog(self.btn_install.get_label(), msg)
                elif not only_on_error:
                    msg = _("The software has been successfully installed.")
                    message_dialog(self.btn_install.get_label(), msg)
        except Exception:
            message_dialog(self.btn_install.get_label(), cmd_output)

    def exec_command(self, command):
        """Execute a command in a separate thread

        Args:
            command (str): command to execute
        """
        try:
            # Run the command in a separate thread
            print((f"Run command: {command}"))
            name = 'aptcmd'
            t = ExecuteThreadedCommands([command], self.queue)
            self.threads[name] = t
            t.daemon = True
            t.start()
            self.queue.join()
            GLib.timeout_add(250, self.check_thread, name)

        except Exception as detail:
            error_dialog(self.btn_install.get_label(), detail)

    def set_buttons_state(self, enable):
        """ Enable/disable buttons """
        if not enable:
            # Get widgets current state
            self.next_saved_state = self.btn_next.get_sensitive()
            self.prev_saved_state = self.btn_previous.get_sensitive()
            self.pb_saved_state = self.pb_welcome.get_fraction()

            # Disable buttons and pulse the progressbar
            self.btn_install.set_sensitive(False)
            self.btn_next.set_sensitive(False)
            self.btn_previous.set_sensitive(False)
        else:
            # Set widgets back to old state
            self.pb_welcome.set_fraction(self.pb_saved_state)
            self.btn_next.set_sensitive(self.next_saved_state)
            self.btn_previous.set_sensitive(self.prev_saved_state)
            self.btn_install.set_sensitive(True)

    def check_thread(self, name):
        """ Check the state of the thread """
        if self.threads[name].is_alive():
            self.pb_welcome.pulse()
            if not self.queue.empty():
                ret = self.queue.get()
                print((f"Queue returns: {ret}"))
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
        """Check with /usr/bin/ddm if we need to install aditional drivers

        Returns:
            boot: True if drivers are needed
        """
        if exists('/usr/bin/ddm'):
            hw_list = ['amd', 'nvidia', 'broadcom', 'pae']
            for hw in hw_list:
                drivers = getoutput(f"ddm -i {hw} -s")
                if drivers[0]:
                    return True
        return False

    # Close the gui
    def on_welcome_window_destroy(self, widget):
        """ Close window """
        # Create flag file
        print((f'touch {self.flag_path}'))
        os.system(f'touch {self.flag_path}')
        # Close the app
        Gtk.main_quit()

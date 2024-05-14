#!/usr/bin/env python3
"""
WebKit1 reference: https://webkitgtk.org/reference/webkitgtk/stable
WebKit2 reference: https://webkitgtk.org/reference/webkit2gtk/stable

Make sure you have WebKit2 2.22.x or higher installed.
For Debian Stretch you need the backports packages:
apt install -t stretch-backports gir1.2-javascriptcoregtk-4.0 gir1.2-webkit2-4.0 libjavascriptcoregtk-4.0-18 libwebkit2gtk-4.0-37  libwebkit2gtk-4.0-37-gtk2

Make sure you have this JavaScript in your HTML when using WebKit2:
<script>
function get_checked_values(class_name) {
    var e = document.getElementsByClassName(class_name); var r = []; var c = 0;
    for (var i = 0; i < e.length; i++) {
        if (e[i].checked) { r[c] = e[i].value; c++;}
    }
    return r;
}
function switch_checked(class_name, check) {
    var js_check = (check.toLowerCase() == 'true');
    var e = document.getElementsByClassName(class_name);
    for (var i = 0; i < e.length; i++) {
        e[i].checked = js_check;
    }
}
</script>
"""

import re
from os.path import exists
import webbrowser
import gi
from gi.repository import GObject

WEBKIT2 = False
WEBKIT2VER = None

try:
    gi.require_version('WebKit2', '4.1')
    WEBKIT2 = True
except ImportError:
    try:
        gi.require_version('WebKit2', '4.0')
        WEBKIT2 = True
    except ImportError:
        gi.require_version('WebKit', '3.0')
        from gi.repository import WebKit
if WEBKIT2:
    from gi.repository import WebKit2 as WebKit
    WEBKIT2VER = WebKit.get_major_version(), WebKit.get_minor_version(), WebKit.get_micro_version()
    if WEBKIT2VER[0] < 2 or \
        WEBKIT2VER[1] < 22:
        WK2VER = '.'.join(map(str, WEBKIT2VER))
        raise ValueError(f'WebKit2 wrong version ({WK2VER}).'
                          ' Upgrade to version 2.22.x or higher')


class SimpleBrowser(WebKit.WebView):
    """Creates a simple browser object"""
    # Create custom signals
    __gsignals__ = {
        "js-finished" : (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
        "html-response-finished" : (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ()),
        "html-load-finished" : (GObject.SignalFlags.RUN_LAST, GObject.TYPE_NONE, ())
    }

    def __init__(self):
        WebKit.WebView.__init__(self)
        # Set properties
        self.uses_webkit2 = WEBKIT2
        self.webkit2_ver = WEBKIT2VER
        self.links_in_browser = True

        # Store JS output
        self.js_values = []
        # Store html response
        self.html_response = ''

        # WebKit2 Signals
        if self.uses_webkit2:
            self.connect('decide-policy', self.on_decide_policy)
            self.connect("load_changed", self.on_load_changed)
            self.connect('button-press-event', lambda w, e: e.button == 3)
        else:
            self.connect('new-window-policy-decision-requested', self.on_nav_request)
            self.connect('resource-load-finished', self.on_resource_load_finished)
            self.connect('button-press-event', lambda w, e: e.button == 3)

        # Settings
        s = self.get_settings()
        if self.uses_webkit2:
            s.set_property('allow_file_access_from_file_urls', True)
            s.set_property('enable-spatial-navigation', False)
            s.set_property('enable_javascript', True)
        else:
            s.set_property('enable-file-access-from-file-uris', True)
            s.set_property('enable-default-context-menu', False)

    def show_html(self, html_or_url, links_in_browser=True):
        """Show HTML in Webview

        Args:
            html_or_url (string): URL, local file path or string
            links_in_browser (bool, optional): Open links in browser. Defaults to True.
        """
        self.links_in_browser = links_in_browser
        if exists(html_or_url):
            match_obj = re.search(r'^file:\/\/', html_or_url)
            if not match_obj:
                html_or_url = f"file://{html_or_url}"
        match_obj = re.search(r'^[a-z]+:\/\/', html_or_url)
        if match_obj:
            if self.uses_webkit2:
                self.load_uri(html_or_url)
            else:
                self.open(html_or_url)
        else:
            if self.uses_webkit2:
                self.load_html(html_or_url)
            else:
                self.load_string(html_or_url, 'text/html', 'UTF-8', 'file://')
        self.show()

    def get_element_values(self, element_name):
        """Get value from given element

        Args:
            element_name (string): name of the element
        """
        self.js_values = []
        if self.uses_webkit2:
            self.js_run(f'get_checked_values(f"{element_name}")', js_return=True)
        else:
            values = []
            doc = self.get_dom_document()
            # https://webkitgtk.org/reference/webkitdomgtk/stable/WebKitDOMDocument.html#webkit-dom-document-get-elements-by-class-name
            # https://webkitgtk.org/reference/webkitdomgtk/stable/WebKitDOMNodeList.html#webkit-dom-node-list-item
            elements = doc.get_elements_by_class_name(element_name)
            for i in range(elements.get_length()):
                # https://webkitgtk.org/reference/webkitdomgtk/stable/WebKitDOMHTMLInputElement.html
                child = elements.item(i)
                if child.get_checked():
                    value = child.get_value().strip()
                    if value:
                        values.append(value)
            # Get return value in line with WebKit2
            self.js_values = values
            self.emit('js-finished')

    def switch_checked_elements(self, element_name, check):
        """Check/uncheck element

        Args:
            element_name (string): name of the element
            check (bool): True (check) or False (uncheck)
        """
        if self.uses_webkit2:
            self.js_run('switch_checked(f"{element_name}", f"{check}")', js_return=False)
        else:
            doc = self.get_dom_document()
            # https://webkitgtk.org/reference/webkitdomgtk/stable/WebKitDOMDocument.html#webkit-dom-document-get-elements-by-class-name
            # https://webkitgtk.org/reference/webkitdomgtk/stable/WebKitDOMNodeList.html#webkit-dom-node-list-item
            elements = doc.get_elements_by_class_name(element_name)
            for i in range(elements.get_length()):
                # https://webkitgtk.org/reference/webkitdomgtk/stable/WebKitDOMHTMLInputElement.html
                elements.item(i).set_checked(check)

    def js_run(self, function_name, js_return=True):
        """Run javascript

        Args:
            function_name (string): name of the javascript function
            js_return (bool, optional): run _js_finish. Defaults to True.
        """
        if self.uses_webkit2:
            # JavaScript
            # https://webkitgtk.org/reference/webkit2gtk/stable/WebKitWebView.html#webkit-web-view-run-javascript
            run_js_finish = self._js_finish if js_return else None
            self.run_javascript(function_name, None, run_js_finish, None)
        else:
            raise TypeError('WebKit2 method only.')

    def _js_finish(self, webview, result, user_data=None):
        """Internal function to finish js"""
        if self.uses_webkit2:
            try:
                # https://webkitgtk.org/reference/webkit2gtk/stable/WebKitWebView.html#webkit-web-view-run-javascript-finish
                js_result = self.run_javascript_finish(result)
                if js_result is not None:
                    # https://webkitgtk.org/reference/jsc-glib/stable/JSCValue.html
                    # Couldn't handle anything but string :(
                    # If returning the getElementsByClassName object itself:
                    # GLib.Error: WebKitJavascriptError:  (699)
                    value = js_result.get_js_value().to_string()
                    if value:
                        self.js_values = value.split(',')
                    #print((self.js_values))
            except Exception as e:
                print((f"JavaScript error: {e}"))
            finally:
                self.emit('js-finished')
        else:
            raise TypeError('WebKit2 method only.')

    def get_response_data(self):
        """ Get html of loaded page """
        if self.uses_webkit2:
            resource = self.get_main_resource()
            resource.get_data(None, self._get_response_data_finish, None)
        else:
            frame = self.get_main_frame()
            # Get return value in line with WebKit2
            self.html_response = frame.get_data_source().get_data()
            self.emit('html-response-finished')

    def  _get_response_data_finish(self, resource, result, user_data=None):
        if self.uses_webkit2:
            # Callback from get_response_data
            self.html_response = resource.get_data_finish(result).decode("utf-8")
            self.emit('html-response-finished')
        else:
            raise TypeError('WebKit2 method only.')

    def on_decide_policy(self, webview, decision, decision_type):
        """ WebKit2: User clicked on a "<a href" link """
        if decision_type == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION:
            action = decision.get_navigation_action()
            action_type = action.get_navigation_type()
            if action_type == WebKit.NavigationType.LINK_CLICKED:
                uri = action.get_request().get_uri()
                if self.links_in_browser:
                    decision.ignore()
                    # Open link in new browser
                    webbrowser.open_new_tab(uri)
                else:
                    # Open link in current webview
                    webview.load_uri(uri)
        else:
            if decision is not None:
                decision.use()

    def on_nav_request(self, webview, frame, request, action, decision):
        """ 
        WebKit1: User clicked on a "<a href" link
        Many external pages don't load well in WebKit1: use external browser only
        """
        reason = action.get_reason()
        if reason == WebKit.WebNavigationReason.LINK_CLICKED:
            if decision is not None:
                uri = request.get_uri()
                decision.ignore()
                webbrowser.open_new_tab(uri)
        else:
            if decision is not None:
                decision.use()

    def on_load_changed(self, webview, event):
        """ WebKit2: signal loading page finished """
        if event == WebKit.LoadEvent.FINISHED:
            self.emit('html-load-finished')

    def on_resource_load_finished(self, webview, frame, resource, user_data=None):
        """ WebKit1: signal loading page finished """
        self.emit('html-load-finished')

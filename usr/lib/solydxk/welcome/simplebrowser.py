#!/usr/bin/env python3
"""
WebKit1 reference: https://webkitgtk.org/reference/webkitgtk/stable
WebKit2 reference: https://webkitgtk.org/reference/webkit2gtk/stable

Make sure you have WebKit2 2.22.x or higher installed.

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
WKVER = None

try:
    gi.require_version('WebKit2', '4.1')
    print(("Using WebKit2 4.1"))
    WEBKIT2 = True
except ValueError as e:
    try:
        gi.require_version('WebKit2', '4.0')
        print(("Using WebKit2 4.0"))
        WEBKIT2 = True
    except ValueError:
        try:
            gi.require_version('WebKit', '6.0')
            print(("Using WebKit 6.0"))
        except ValueError:
            try:
                gi.require_version('WebKit', '3.0')
                print(("Using WebKit 3.0"))
            except ValueError as exc:
                raise e from exc
try:
    if WEBKIT2:
        from gi.repository import WebKit2 as WebKit
    else:
        from gi.repository import WebKit
except ImportError as e:
    raise e

# Get version information
WKVER = WebKit.get_major_version(), WebKit.get_minor_version(), WebKit.get_micro_version()
VER_STR = '.'.join(map(str, WKVER))
print((f"WebKit version: {VER_STR}"))
if WEBKIT2 and (WKVER[0] == 2 and WKVER[1] < 22):
    raise ValueError(f'WebKit2 wrong version ({VER_STR}).'
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
        self.webkit_ver = WKVER
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
            self.js_run(f"get_checked_values('{element_name}')", js_return=True)
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
            self.js_run(f"switch_checked('{element_name}', '{check}')", js_return=False)
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
            # https://webkitgtk.org/reference/webkit2gtk/stable/method.WebView.evaluate_javascript.html
            run_js_finish = self._js_finish if js_return else None
            # Deprecated from 2.40: run_javascript(function_name, None, run_js_finish, None)
            self.evaluate_javascript(script=function_name,
                                     length=-1,
                                     world_name=None,
                                     source_uri=None,
                                     cancellable=None,
                                     callback=run_js_finish)
        else:
            raise TypeError('WebKit2 method only.')

    def _convert_js_value(self, js_value):
        if not js_value or js_value.is_null() or js_value.is_undefined():
            return None
        elif js_value.is_boolean():
            return js_value.to_boolean()
        elif js_value.is_number():
            return js_value.to_double()
        elif js_value.is_string():
            return js_value.to_string()
        elif js_value.is_array():
            value = js_value.to_string()
            return value.split(',') if value else []
        elif js_value.is_object():
            js_object = js_value.to_object()
            python_dict = {}
            properties = js_object.get_property_names()
            for prop in properties:
                python_dict[prop] = self._js_value_to_python(js_object.get_property(prop))
            return python_dict
        else:
            print((f'Unsupported JavaScriptCore.Value type: {js_value}'))
            return js_value.to_string()

    def _js_finish(self, webview, result, user_data=None):
        """Internal function to finish js"""
        if self.uses_webkit2:
            try:
                # https://webkitgtk.org/reference/webkit2gtk/stable/method.WebView.evaluate_javascript_finish.html
                # Deprecated from 2.40: run_javascript_finish(result)
                js_result = self.evaluate_javascript_finish(result=result)
                self.js_values = self._convert_js_value(js_result)
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

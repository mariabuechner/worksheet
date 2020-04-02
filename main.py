"""
GUI module for worksheet generator.

Usage
#####

python mainGUI.py [Option...]::
    -d, --debug     show debug logs

@author: buechner_m  <maria.buechner@gmail.com>
"""
import numpy as np
import random
from functools import partial
import sys
import re
import os.path
import datetime
import logging
import names # random names generator
# Set kivy logger console output format
formatter = logging.Formatter('%(asctime)s - %(name)s -    %(levelname)s - '
                              '%(message)s')
console = logging.StreamHandler()
console.setFormatter(formatter)
sys._kivy_logging_handler = console
import kivy
kivy.require('1.11.1')  # Checks kivy version
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.logger import Logger
from kivy.app import App
from kivy.clock import Clock
from kivy.garden.filebrowser import FileBrowser
from kivy.core.window import Window
from kivy.factory import Factory as F  # Widgets etc. (UIX)
# Logging
# Set logger before importing (simulation) modules (to set format for all
# loggers)
logging.Logger.manager.root = Logger  # Makes Kivy Logger root for all
                                      # following loggers
logger = logging.getLogger(__name__)

# Set App Window configuration
Window.maximize() # NOTE: On desktop platforms only
# %% Constants

ERROR_MESSAGE_SIZE = (600, 450)  # absolute
FILE_BROWSER_SIZE = (0.9, 0.9)  # relative
LINE_HEIGHT = 35
TAB_HEIGHT = 1200

# #############################################################################
# FileBrowser #################################################################
# Does not work with globally modified Label, use custom label for everything
# else


class NonFileBrowserLabel(F.Label):
    """
    Custom Label to avoid conflict with FileBrowser and allow global changes,
    defined in .kv.
    """
    pass


class ScrollableLabel(F.ScrollView):
    """
    Label is scrolable in y direction. See .kv file for more information.
    """
    text = F.StringProperty('')

# #############################################################################
# Error and warning popups ####################################################


class ErrorDisplay():
    """
    Popup window in case an exception is caught. Displays type of error and
    error message.

    Parameters
    ==========

    error_title [str]:      type of error
    error_message [str]:    error message

    """
    def __init__(self, error_title, error_message):
        """
        Init _OKPopupWindow and open popup.
        """
        error_popup = _OKPopupWindow(error_title, error_message)
        error_popup.popup.open()


class WarningDisplay():
    """
    Popup window in case an exception is caught and user can choose to
    continue. Displays type of warning and warning message.

    Parameters
    ==========

    warning_title [str]:        type of warning
    warning_message [str]:      warning message

    overwrite [func]:           function to execute if 'continue'
    overwrite_finish [func]:    after overwrite, finish up
    cancel_finish [func]:       after cancel, finish up

    """
    def __init__(self, warning_title, warning_message,
                 overwrite, overwrite_finish,
                 cancel_finish):
        """
        Init _ContinueCancelPopupWindow and open popup.
        """
        self.warning_popup = _ContinueCancelPopupWindow(warning_title,
                                                        warning_message,
                                                        overwrite,
                                                        overwrite_finish,
                                                        cancel_finish)
        self.warning_popup.popup.open()


class LabelHelp(NonFileBrowserLabel):
    """
    Label, but upon touch down a help message appears.

    Parameters
    ==========

    help_message [StringProperty]

    """
    help_message = F.StringProperty()

    def on_touch_down(self, touch):
        """
        On touch down a popup window is created, with its title indicating
        the variable to which the help is referring and its help message.

        """
        # If mouse clicked on
        if self.collide_point(touch.x, touch.y):
            window_title = 'Help: {}'.format(self.text)
            help_popup = _OKPopupWindow(window_title, self.help_message)
            help_popup.popup.open()
        # To manage input chain corectly
        return super(LabelHelp, self).on_touch_down(touch)

# #############################################################################
# Inputs ######################################################################


class IntInput(F.TextInput):
    """
    TextInput which only allows positive integers.
    """

    pattern = re.compile('[^0-9]')  # Allowed input numbers

    def insert_text(self, substring, from_undo=False):
        """
        Overwrites the insert_text function to only accept numbers 0...9.
        """
        pattern = self.pattern
        s = re.sub(pattern, '', substring)
        return super(IntInput, self).insert_text(s, from_undo=from_undo)


# #############################################################################
# Popups # ####################################################################


class _OKPopupWindow():
    """
    A popup window containing a label and a button.

    The button closes the window.

    Parameters
    ==========

    title [str]:    title of popup window
    message [str]:  message displayed

    """
    def __init__(self, title, message):
        """
        Init function, creates layout and adds functunality.

        """
        # Custom Window with close button
        popup_content = F.BoxLayout(orientation='vertical',
                                    spacing=10)

        message_label = F.ScrollableLabel(text=message)
        popup_content.add_widget(message_label)
        close_popup_button = F.Button(text='OK')

        popup_content.add_widget(close_popup_button)

        self.popup = F.Popup(title=title,
                             title_size=20,
                             auto_dismiss=False,
                             content=popup_content,
                             size_hint=(None, None),
                             size=ERROR_MESSAGE_SIZE)
        close_popup_button.bind(on_press=self.popup.dismiss)


class _ContinueCancelPopupWindow():
    """
    A popup window containing a label and 2 buttons (cancel and continue).


    Parameters
    ==========

    title [str]:    title of popup window
    message [str]:  message displayed

    Notes
    =====

    _continue stores the choice, True if continue, False if cancel.

    """
    def __init__(self, title, message,
                 overwrite, overwrite_finish,
                 cancel_finish):
        """
        Init function, creates layout and adds functunality.
        """
        # Init continuation state
        self._continue = False
        self.overwrite = overwrite
        self.overwrite_finish = overwrite_finish
        self.cancel_finish = cancel_finish
        # Custom Window with continue and cancel button
        popup_content = F.BoxLayout(orientation='vertical',
                                    spacing=10)

        message_label = F.ScrollableLabel(text=message)
        popup_content.add_widget(message_label)

        button_layout = F.BoxLayout(spacing=10)
        cancel_popup_button = F.Button(text='Cancel')
        continue_popup_button = F.Button(text='Continue')

        button_layout.add_widget(continue_popup_button)
        button_layout.add_widget(cancel_popup_button)

        popup_content.add_widget(button_layout)

        self.popup = F.Popup(title=title,
                             title_size=20,
                             auto_dismiss=False,
                             content=popup_content,
                             size_hint=(None, None),
                             size=ERROR_MESSAGE_SIZE)

        # Close help window when button 'OK' is pressed
        continue_popup_button.bind(on_press=partial(self.close, True))
        cancel_popup_button.bind(on_press=partial(self.close, False))

        self.popup.bind(on_dismiss=self.finish)  # Wait for dismiss

    def close(self, *args):
        """
        Executed on press of any button, stores continuation indicator.

        Parameters
        ==========

        continue_ [boolean]:    Continue (True) with action or cancel (False)
                                action

        """
        self._continue = args[0]
        self.popup.dismiss()

    def finish(self, *args):
        """
        Finishing function bound to popup's dismiss. If 'continue' was pressed,
        execute 'overwrite()' and the 'overwrite_finish()', else the
        'cancel_finish'.
        """
        if self._continue:
            logger.info("Overwriting file!")
            self.overwrite()
            logger.info('... done.')
            self.overwrite_finish()
        else:
            logger.info("... canceled.")
            self.cancel_finish()

# #############################################################################
# Save worksheet # ############################################################


# #############################################################################
# Handle exceptions # #########################################################


class _IgnoreExceptions(ExceptionHandler):
    """
    Kivy Exception Handler to either display the exception or exit the
    program.

    """
    def handle_exception(self, inst):
        """
        Exception Handler disabeling the automatic exiting after any exception
        occured.
        Now: pass. Python needs to handlen all exceptions now.
        """
        return ExceptionManager.PASS

# If kivy is NOT set to debug, disable kivy error handling, so that the errors
# pop up
if Logger.level > 10:
    ExceptionManager.add_handler(_IgnoreExceptions())


# %% Main GUI

class WorksheetGUI(F.StackLayout):
    """
    Main Widget, BoxLayout

    Notes
    =====

    File loading and saving based on
    "https://kivy.org/docs/api-kivy.uix.filechooser.html" (23.10.2017)

    Kivy properties necessary if check if changed or access at .kv is
    necessary.

    """
    # "Global kivy" variables (if kivy ..Property() sharable in .kv)
    # params[var_name] = value
    current_date = F.StringProperty()
    current_week = F.StringProperty()
    user_name = F.StringProperty()
    current_worksheet = F.StringProperty()

    def __init__(self, **kwargs):
        super(WorksheetGUI, self).__init__(**kwargs)

        self.current_date = datetime.date.today().strftime("%d.%m.%Y")
        self._list_filetypes = [".xlsx", ".csv"]

    # Wisgets reaction to change
    def generate_worksheet(self):
        """
        Generate worksheet string

        Format
        ======

        header:         Date, Name, calendar week
        Tasks:          Randomly generated

        """
        # Header (date, name, week)
        if not self.user_name:
            self.ids.user.text = str(names.get_full_name())
            warning_message = ("No user name entered, substituting {} ..."
                               .format(self.user_name))
            logger.warning(warning_message)
            ErrorDisplay('Generating random name', warning_message)
        if not self.current_week:
            warning_message = ("Work week not selected, using current ...")
            logger.warning(warning_message)
            ErrorDisplay('Using current work week', warning_message)
            self.ids.current_week.active = True
        header = ("Date: {0}\nName: {1}\nWork week: {2}"
                  .format(self.current_date, self.user_name,
                          self.current_week))
        # Tasks
        tasks = 'Tasks:\n\n'
        tasks = ("{0}{1}".format(tasks,self.generate_tasks()))

        # Display
        self.current_worksheet = '{0}\n\n{1}'.format(header, tasks)
        self.ids.display_worksheet.text = self.current_worksheet

    def save_worksheet(self):
        """
        Save worksheet string to file

        """
        if not self.current_worksheet:
            error_message = ("Current worksheet is empty, please generate "
                             "first.")
            logger.error(error_message)
            ErrorDisplay('Worksheet Error', error_message)
        else:
            pass

    # Taks generaton
    def generate_tasks(self):
        """
        Generate random tasks

        Notes
        =====

        Random number of tasks between 4 and 10

        """
        taskfile = open("tasks.txt","r")
        task_list = taskfile.read()
        taskfile.close()
        # get tasks for each focus group that has been selected
        tasks = list()
        for widget_id, widget in self.ids.iteritems():
            if 'fg_' in widget_id and self.ids[widget_id].active:
                current_tasks = task_list.split(widget_id+':')[1]
                current_tasks = current_tasks.split('\n\nfg')[0]
                current_tasks = current_tasks.splitlines()[1:]
                number_of_tasks = np.random.randint(4, 10, 1)[0]
                current_tasks = [current_tasks[i] for i in
                                 random.sample(range(0, len(current_tasks)),
                                               number_of_tasks)]
                tasks.extend(current_tasks)
        # If empty (nothing selected) ...
        if tasks == []:
            warning_message = ("No focus group selected, tasks list empty.")
            logger.warning(warning_message)
            ErrorDisplay('Please select focus group', warning_message)

        # Convert to string
        tasks = '\n'.join(tasks)
        return tasks








class WorksheetApp(App):
    def build(self):
        return WorksheetGUI()


if __name__ == '__main__':
    WorksheetApp().run()

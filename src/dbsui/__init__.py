#!/usr/bin/env python3
# Copyright (c) 2021, Al Stone <ahs3@ahs3.net>
#
#       dbs == dain-bread simple, a todo list for minimalists
#
# SPDX-License-Identifier: GPL-2.0-only
#

import collections
import curses
from curses import panel

import dbs_task
from dbs_task import *

import datetime
import editor
import os
import os.path
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

#-- globals
HELP_PREFIX = re.compile('^help_')

ACTIVE_PROJECTS = collections.OrderedDict()
ACTIVE_TASKS = collections.OrderedDict()
ALL_PROJECTS = collections.OrderedDict()
ALL_TASKS = collections.OrderedDict()

current_project = ''
current_task = ''
current_line = ''

BOLD_BLUE_ON_BLACK = None
BOLD_GREEN_ON_BLACK = None
BOLD_PLAIN_TEXT = None
BOLD_RED_ON_BLACK = None
BOLD_WHITE_ON_BLUE = None
BOLD_WHITE_ON_RED = None

BLUE_ON_BLACK = None
GREEN_ON_BLACK = None
PLAIN_TEXT = None
RED_ON_BLACK = None
WHITE_ON_BLUE = None
WHITE_ON_RED = None

HIGH = 'h'
MEDIUM = 'm'
LOW = 'l'

CLI_PANEL     = 'cli'
HEADER_PANEL  = 'hdr'
LIST_PANEL    = 'lst'
PROJ_PANEL    = 'prj'
TASK_PANEL    = 'tsk'
TRAILER_PANEL = 'trlr'

ACTIVE_TASKS_TRAILER  = ' Active Tasks: %d || j: Next   k: Previous   q: Quit '
ALL_TASKS_TRAILER     = ' All Tasks: %d || j: Next   k: Previous   q: Quit '
DELETED_TASKS_TRAILER = ' Deleted Tasks: %d || j: Next   k: Previous   q: Quit '
DONE_TASKS_TRAILER    = ' Done Tasks: %d || j: Next   k: Previous   q: Quit '
HELP_HEADER           = 'Help || j: NextLine   k: PrevLine  q: Quit'
OPEN_TASKS_TRAILER    = ' Open Tasks: %d || j: Next   k: Previous   q: Quit '
MAIN_HEADER           = 'dbs || q: Quit   s: Show Task   ?: Help'
RECAP_HEADER          = 'Recap || j: NextLine   k: PrevLine  q: Quit'
SHOW_HEADER           = 'Show Task || j: NextLine   k: PrevLine  q: Quit'
STATE_COUNTS_HEADER   = 'Project  Active  Open  Done  Deleted   Total'
TASKS_HEADER          = '--- Name  Project  Note  P  Task'

VERSION_TEXT        = 'dbsui, v' + dbs_task.VERSION + ' '

DBG = None
PROJECT_WIDTH = 20

#-- classes
class DbsLine:
    def __init__(self, name, screen, content_cb):
        # basic initialization
        self.name = name
        self.content_cb = content_cb
        self.content = []
        self.text = ''

        self.screen = screen
        self.window = None
        self.panel = None
        return
    
    def create(self):
        # create the window -- needs replacing for each panel type
        print("create not implemented")
        return

    def create_win(self, height, width, y, x):
        global DBG
        # create the window

        # how big is the screen?
        maxy, maxx = self.screen.getmaxyx()
        DBG.write('create_%s: maxy, maxx: %d, %d' % (self.name, maxy, maxx))

        # create the window
        self.window = self.screen.subwin(height, width, y, x)
        self.panel = curses.panel.new_panel(self.window)
        DBG.write('%s: h,w,y,x: %d, %d, %d, %d' % 
                  (self.name, height, width, y, x))
        self.window.clear()
        self.page_height = height
        return

    def refresh(self):
        # refresh the window content -- needs replacing for each panel type
        print("refresh not implemented")
        return

    def resize(self, screen):
        del self.panel
        del self.window
        self.screen = screen
        self.create()
        return

    def set_text(self, msg):
        self.text = msg
        return

    def get_text(self):
        return self.text


class DbsPanel(DbsLine):
    def __init__(self, name, screen, content_cb):
        # basic initialization
        super(DbsPanel, self).__init__(name, screen, content_cb)
        self.current_index = 0
        self.current_page = 0
        self.page_height = 0
        self.hidden = False

        self.previous_index = self.current_index
        self.previous_page = self.current_page
        self.previous_hidden = self.hidden
        self.previous_text = self.text
        self.previous_content = self.content
        return
    
    def hide(self):
        # hide the window and content
        self.hidden = True
        self.panel.hide()
        return

    def show(self):
        # show the window and content
        self.hidden = False
        self.panel.show()
        return

    def next(self):
        global DBG

        if not self.content:
            return 

        # go to next line of content
        self.current_index += 1
        if self.current_index > len(self.content) - 1:
            self.current_index = len(self.content) - 1

        # move down one line, page if needed
        last_line = ((self.current_page + 1) * (self.page_height - 1))
        if self.current_index >= last_line:
            self.current_page += 1
        maxpage = len(self.content) / self.page_height
        if self.current_page > maxpage:
            self.current_page = maxpage

        DBG.write('next: index %d, page %d, height %d' %
                  (self.current_index, self.current_page, self.page_height))
        return

    def prev(self):
        global DBG

        if not self.content:
            return 

        # go to previous line of content
        self.current_index -= 1
        if self.current_index < 0:
            self.current_index = 0

        # move up one line, page if needed
        first_line = (self.current_page * (self.page_height - 1))
        if self.current_index < first_line:
            self.current_page -= 1
        if self.current_page < 0:
            self.current_page = 0

        DBG.write('prev: index %d, page %d, height %d' %
                  (self.current_index, self.current_page, self.page_height))
        return

    def next_page(self):
        global DBG

        if not self.content:
            return 

        # go to next page of content
        self.current_index += (self.page_height - 1)
        if self.current_index > len(self.content) - 1:
            self.current_index = len(self.content) - 1

        # move down one line, page if needed
        last_line = ((self.current_page + 1) * (self.page_height - 1))
        if self.current_index >= last_line:
            self.current_page += 1
            self.current_index = last_line
        maxpage = len(self.content) / (self.page_height - 1)
        if self.current_page > maxpage:
            self.current_page = maxpage

        DBG.write('next_page: index %d, page %d, height %d' %
                  (self.current_index, self.current_page, self.page_height))
        return

    def prev_page(self):
        global DBG, current_line

        if not self.content:
            return 

        # go to previous page of content
        self.current_index -= (self.page_height - 1)

        # move up one line, page if needed
        first_line = (self.current_page * (self.page_height - 1))
        if self.current_index <= first_line:
            self.current_page -= 1
            self.current_index = (self.current_page * (self.page_height - 1))
        if self.current_page < 0:
            self.current_page = 0
        if self.current_index < 0:
            self.current_index = 0

        DBG.write('prev_page: index %d, page %d, height %d' %
                  (self.current_index, self.current_page, self.page_height))
        return

    def save_previous(self):
        self.previous_index = self.current_index
        self.previous_page = self.current_page
        self.previous_hidden = self.hidden
        self.previous_text = self.text
        self.previous_content = self.content
        return

    def restore_previous(self):
        self.current_index = self.previous_index
        self.current_page = self.previous_page
        self.hidden = self.previous_hidden
        self.text = self.previous_text
        self.content = self.previous_content
        return


class DbsHeader(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsHeader, self).__init__(name, screen, content_cb)
        self.create()
        return

    def create(self):
        maxy, maxx = self.screen.getmaxyx()
        super(DbsHeader, self).create_win(1, maxx, 0, 0)
        return

    def refresh(self):
        self.content_cb(self.screen, self.window, self.text)
        DBG.write('DbsHeader.refresh: msg = "%s"' % (self.text.strip()))
        return

    def set_text(self, hdr, topic):
        maxy, maxx = self.window.getmaxyx()
        blanks = ''.ljust(maxx-1, ' ')
        msg = hdr + blanks[0:maxx-len(topic)-len(hdr)-1]
        self.text = msg + topic
        return


class DbsTrailer(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsTrailer, self).__init__(name, screen, content_cb)
        self.create()
        return

    def create(self):
        maxy, maxx = self.screen.getmaxyx()
        super(DbsTrailer, self).create_win(1, maxx, maxy-2, 0)
        return

    def refresh(self):
        self.content_cb(self.screen, self.window, self.text)
        return


class DbsCli(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsCli, self).__init__(name, screen, content_cb)
        self.create()
        return

    def create(self):
        maxy, maxx = self.screen.getmaxyx()
        super(DbsCli, self).create_win(1, maxx, maxy-1, 0)
        return

    def refresh(self):
        self.content_cb(self.screen, self.window, self.text)
        return

    def move_cursor(self):
        self.window.move(0, len('Add note: '))
        return

    def get_response(self, prompt):
        global DBG

        if not prompt:
            prompt = '> '
        win = self.window
        win.clear()
        curses.curs_set(2)
        curses.echo()
        win.move(0, 0)
        win.addstr(0, 0, prompt, BOLD_RED_ON_BLACK)
        win.refresh()

        buf = win.getstr(0, len(prompt))
        txt = ''
        for ii in buf[0:]:
            txt += chr(ii)

        curses.curs_set(0)
        curses.noecho()
        return txt


class DbsProjects(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsProjects, self).__init__(name, screen, content_cb)
        self.create()
        self.current_project = ''
        self.populate()
        return

    def create(self):
        maxy, maxx = self.screen.getmaxyx()
        self.page_height = maxy - 2
        width = PROJECT_WIDTH
        super(DbsProjects, self).create_win(self.page_height, width, 1, 0)
        return

    def refresh(self):
        global current_project, current_task
        global DBG

        if self.hidden:
            return

        start = self.current_page * (self.page_height - 1)
        plist = self.content[start:]
        DBG.write('DbsProject::refresh: "%s", first, last = %d, %d' %
                  (current_project, start, len(self.content)-1))
        current_project = self.current_project
        self.content_cb(self.screen, self.window, plist)
        return

    def populate(self):
        global ACTIVE_PROJECTS, current_project
        global DBG

        plist = []
        for ii in ACTIVE_PROJECTS.keys():
            p = ACTIVE_PROJECTS[ii]
            pname = ii[0:PROJECT_WIDTH-1]
            active = p[ACTIVE]
            if active > 0:
                line = "%s\t[%d]" % (pname, active)
            else:
                line = "%s" % (pname)
            plist.append(line)

        self.content = sorted(plist)
        if not self.current_project and len(self.content) > 0:
            self.current_project = self.content[0].split('\t')[0]
        if not current_project:
            current_project = self.current_project
        return

    def next_project(self):
        global current_project

        if not self.content:
            return 

        self.next()
        self.current_project = self.content[self.current_index].split('\t')[0]
        current_project = self.current_project

        return

    def prev_project(self):
        global current_project

        if not self.content:
            return 

        self.prev()
        self.current_project = self.content[self.current_index].split('\t')[0]
        current_project = self.current_project

        return


class DbsTasks(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsTasks, self).__init__(name, screen, content_cb)
        self.create()
        self.current_task = ''
        self.populate()
        return

    def create(self):
        maxy, maxx = self.screen.getmaxyx()
        self.page_height = maxy - 2
        self.page_width = maxx - PROJECT_WIDTH
        super(DbsTasks, self).create_win(self.page_height, self.page_width,
                     1, PROJECT_WIDTH)
        return

    def refresh(self):
        global current_task
        global DBG

        if not self.content:
            return 

        if self.hidden:
            self.current_index = 0
            self.current_page = 0
            current_task = self.content[self.current_index].split('\t')[0]
            return

        start = self.current_page * (self.page_height - 1)
        plist = self.content[start:]
        DBG.write('DbsTasks::refresh: first, last, height = %d, %d, %d' %
                  (start, len(self.content)-1, self.page_height))
        self.content_cb(self.screen, self.window, plist)
        return

    def populate(self):
        global ACTIVE_TASKS, current_project, current_task

        tlist0 = get_current_task_list(current_project)
        if not tlist0:
            return

        tlist = {HIGH:[], MEDIUM:[], LOW:[] }
        for ii in tlist0:
            t = ACTIVE_TASKS[ii]
            tlist[t.get_priority()].append(t)

        clist = []
        for ii in [HIGH, MEDIUM, LOW]:
            for jj in sorted(tlist[ii]):
                info = '%8.8s' % jj.get_name()
                if jj.note_count() > 0:
                    info += '\t[%2d]' % jj.note_count()
                else:
                    info += '\t    '
                info += '\t%s' % jj.get_priority()
                info += '\t%s' % jj.get_task()
                if jj.get_state() == ACTIVE:
                    info += '\tACTIVE'
                clist.append(info)

        self.content = clist
        if len(self.content) > 0:
            self.current_task = self.content[0].split('\t')[0]
        current_task = self.current_task
        self.current_index = 0
        self.current_page = 0
        return

    def next_task(self):
        global current_task

        if not self.content:
            return

        self.next()
        self.current_task = self.content[self.current_index].split('\t')[0]
        current_task = self.current_task

        return

    def prev_task(self):
        global current_task

        if not self.content:
            return

        self.prev()
        self.current_task = self.content[self.current_index].split('\t')[0]
        current_task = self.current_task

        return

    def remove_task(self, task_name):
        global DBG

        DBG.write('try to remove_task: "%s"' % task_name)
        if not self.content:
            return
        else:
            if task_name in self.content:
                del self.content[task_name]
                DBG.write('remove_task done: "%s"' % task_name)


class DbsList(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsList, self).__init__(name, screen, content_cb)
        self.create()
        self.current_project = ''
        self.populate()
        return

    def create(self):
        maxy, maxx = self.screen.getmaxyx()
        self.page_height = maxy - 2
        width = maxx - 1
        self.page_width = width
        super(DbsList, self).create_win(self.page_height, width, 1, 0)
        return

    def refresh(self):
        global current_project
        global DBG

        if self.hidden:
            return

        if not self.content:
            return 

        start = self.current_page * (self.page_height - 1)
        if start > len(self.content) - 1:
            start = len(self.content) - 1
        plist = self.content[int(start):]
        DBG.write('DbsList::refresh: first, last = %d, %d' %
                  (start, len(self.content)-1))
        self.content_cb(self.screen, self.window, plist)
        return

    def set_content(self, clist):
        global DBG, current_line

        self.window.clear()
        self.content = clist
        self.current_index = 0
        self.current_page = 0
        current_line = self.content[self.current_index]
        #DBG.write('set_content: line = "%s"' % current_line)
        #DBG.write('set_content: content\n%s' % '\n'.join(self.content))
        return

    def populate(self):
        return

    def next(self):
        global current_line

        if not self.content:
            return 

        super(DbsList, self).next()
        current_line = self.content[self.current_index]

        return

    def prev(self):
        global current_line

        if not self.content:
            return 

        super(DbsList, self).prev()
        current_line = self.content[self.current_index]

        return

    def next_page(self):
        global current_line

        if not self.content:
            return 

        super(DbsList, self).next_page()
        current_line = self.content[int(self.current_index)]

        return

    def prev_page(self):
        global current_line

        if not self.content:
            return 

        super(DbsList, self).prev_page()
        current_line = self.content[int(self.current_index)]

        return

    def save_previous(self):
        global current_line

        super(DbsList, self).save_previous()
        self.prev_line = current_line

        return

    def restore_previous(self):
        global current_line

        super(DbsList, self).restore_previous()
        current_line = self.prev_line

        return


class Debug:
    def __init__(self):
        self.fd = open('debug.log', 'w')
        return

    def write(self, msg):
        self.fd.write("%s\n" % msg)
        return

    def done(self):
        self.fd.close()
        return

#-- command functions
def add_task(tname):
    global DBG, ALL_TASKS, current_project

    ret = ''
    task_name = dbs_task.task_canonical_name(tname)
    if task_name in ALL_TASKS:
        return ('? task %d already exists' % int(task_name))

    t = Task()
    t.set_name(task_name)
    t.set_project(current_project)
    t.set_priority(MEDIUM)
    t.set_state(OPEN)
    DBG.write('add_task: %s' % task_name)

    # copy the file to a temporary location
    before_edit = t.show_text()
    tfd, tpath = tempfile.mkstemp(text=True)
    before = bytearray()
    before.extend(before_edit.encode("utf-8"))
    os.write(tfd, before)
    os.fsync(tfd)

    # pop the editor onto the screen
    editor = os.environ['EDITOR']
    if not editor:
        editor = 'vi'
    result = subprocess.run([editor, tpath])
    os.lseek(tfd, 0, 0)
    after = os.read(tfd, os.fstat(tfd).st_size)
    os.close(tfd)
    try:
        os.remove(tpath)
    except OSError:
        pass

    # verify the task content
    after_edit = after.decode("utf-8").split('\n')[0:-1]
    DBG.write('add_task: new text is:\n%s' % (after_edit))
    ret = t.validate(after_edit)

    # report an error if needed
    if len(ret) == 0:
        t.set_fields(after_edit)
        t.add_note('added')
        t.write()

    DBG.write('add_task: %s = %d [%s]' % (task_name, len(after_edit), ret))
    return ret

def log_task(tname):
    global DBG, ALL_TASKS, current_project

    ret = ''
    task_name = dbs_task.task_canonical_name(tname)
    if task_name in ALL_TASKS:
        return ('? task %d already exists' % int(task_name))

    t = Task()
    t.set_name(task_name)
    t.set_project(current_project)
    t.set_priority(MEDIUM)
    t.set_state(DONE)
    DBG.write('log_task: %s' % task_name)

    # copy the file to a temporary location
    before_edit = t.show_text()
    tfd, tpath = tempfile.mkstemp(text=True)
    before = bytearray()
    before.extend(before_edit.encode("utf-8"))
    os.write(tfd, before)
    os.fsync(tfd)

    # pop the editor onto the screen
    editor = os.environ['EDITOR']
    if not editor:
        editor = 'vi'
    result = subprocess.run([editor, tpath])
    os.lseek(tfd, 0, 0)
    after = os.read(tfd, os.fstat(tfd).st_size)
    os.close(tfd)
    try:
        os.remove(tpath)
    except OSError:
        pass

    # verify the task content
    after_edit = after.decode("utf-8").split('\n')[0:-1]
    DBG.write('log_task: new text is:\n%s' % (after_edit))
    ret = t.validate(after_edit)

    # report an error if needed
    if len(ret) == 0:
        t.set_fields(after_edit)
        t.add_note('logged')
        t.write()

    DBG.write('log_task: %s = %d [%s]' % (task_name, len(after_edit), ret))
    return ret

def mark_active(raw_task):
    global ALL_TASKS

    tname = dbs_task.task_canonical_name(raw_task)
    if tname in ALL_TASKS:
        t = ALL_TASKS[tname]
        fullpath = dbs_task.task_name_exists(tname)
        old_state = t.get_state()
        t.set_state(ACTIVE)
        t.add_note("marked active")
        dbs_task.put_task(t)
        if old_state != ACTIVE:
            os.remove(fullpath)
    else:
        return ('? no such task: %d' % int(raw_task))

    return

def mark_deleted(raw_task):
    global ALL_TASKS
    global current_task

    tname = dbs_task.task_canonical_name(raw_task)
    if tname in ALL_TASKS:
        t = ALL_TASKS[tname]
        fullpath = dbs_task.task_name_exists(tname)
        old_state = t.get_state()
        t.set_state(DELETED)
        t.add_note("deleted")
        dbs_task.put_task(t)
        if old_state != DELETED:
            os.remove(fullpath)
    else:
        return ('? no such task: %d' % int(raw_task))

    return

def mark_done(raw_task):
    global ALL_TASKS

    tname = dbs_task.task_canonical_name(raw_task)
    if tname in ALL_TASKS:
        t = ALL_TASKS[tname]
        fullpath = dbs_task.task_name_exists(tname)
        old_state = t.get_state()
        t.set_state(DONE)
        t.add_note("marked done")
        dbs_task.put_task(t)
        if old_state != DONE:
            os.remove(fullpath)
    else:
        return ('? no such task: %d' % int(raw_task))

    return

def mark_higher(raw_task):
    global ALL_TASKS

    tname = dbs_task.task_canonical_name(raw_task)
    if tname in ALL_TASKS:
        t = ALL_TASKS[tname]
        pri = t.get_priority()
        if pri == LOW:
            pri = MEDIUM
        elif pri == MEDIUM:
            pri = HIGH
        else:
            return ("? task \"%s\" already at '%s'" % (int(raw_task), HIGH))
        t.set_priority(pri)
        t.add_note("upped priority")
        dbs_task.put_task(t)
    else:
        return ('? no such task: %d' % int(raw_task))

    return

def mark_inactive(raw_task):
    global ALL_TASKS

    tname = dbs_task.task_canonical_name(raw_task)
    if tname in ALL_TASKS:
        t = ALL_TASKS[tname]
        fullpath = dbs_task.task_name_exists(tname)
        old_path = t.get_state()
        t.set_state(OPEN)
        t.add_note("marked inactive")
        dbs_task.put_task(t)
        if old_state != OPEN:
            os.remove(fullpath)
    else:
        return ('? no such task: %d' % int(raw_task))

    return

def mark_lower(raw_task):
    global ALL_TASKS

    tname = dbs_task.task_canonical_name(raw_task)
    if tname in ALL_TASKS:
        t = ALL_TASKS[tname]
        pri = t.get_priority()
        if pri == HIGH:
            pri = MEDIUM
        elif pri == MEDIUM:
            pri = LOW
        else:
            return ("? task \"%s\" already at '%s'" % (int(raw_task), HIGH))
        t.set_priority(pri)
        t.add_note("upped priority")
        dbs_task.put_task(t)
    else:
        return ('? no such task: %d' % int(raw_task))

    return

def refresh_recap(days):
    if int(days) > int(DAYS_LIMIT):
        return ("? no, you really don't want more than %d days worth." %
               int(days))

    current_time = time.time()
    elapsed_time = int(days) * 3600 * 24

    fullpath = os.path.join(dbs_repo(), DONE)
    tasks = {}
    for (dirpath, dirnames, filenames) in os.walk(fullpath):
        for ii in filenames:
           file_time = os.path.getmtime(os.path.join(fullpath, ii))

           if current_time - file_time < elapsed_time:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               tasks[ii] = t

    clist = []
    if len(tasks) < 1:
        clist.append("No %s tasks found." % DONE)
    else:
        if int(days) == 1:
            clist.append("Done during the last day:")
        else:
            clist.append("Done over the last %d days:" % int(days))
        for pri in [HIGH, MEDIUM, LOW]:
            for ii in sorted(tasks):
               if tasks[ii].get_priority() == pri:
                    info = '%8d  ' % int(tasks[ii].get_name())
                    if tasks[ii].get_state() == DELETED:
                        info += '%1.1s  ' % 'D'
                    else:
                        info += '%1.1s  ' % tasks[ii].get_state()[0:1]
                    info += '%7.7s  ' % tasks[ii].get_project()
                    if tasks[ii].note_count() > 0:
                        info += '[%.2d]  ' % tasks[ii].note_count()
                    else:
                        info += '      '
                    info += '%1s  ' % tasks[ii].get_priority()
                    info += '%s' % tasks[ii].get_task()
                    clist.append(info)

    fullpath = os.path.join(dbs_repo(), ACTIVE)
    tasks.clear()
    for (dirpath, dirnames, filenames) in os.walk(fullpath):
        for ii in filenames:
           file_time = os.path.getmtime(os.path.join(fullpath, ii))

           if current_time - file_time < elapsed_time:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               tasks[ii] = t

    clist.append("")
    if len(tasks) < 1:
        clist.append("No %s tasks touched." % ACTIVE)
    else:
        if int(days) == 1:
            clist.append("Active during the last day:")
        else:
            clist.append("Active over the last %d days:" % int(days))
        for pri in [HIGH, MEDIUM, LOW]:
            for ii in sorted(tasks):
               if tasks[ii].get_priority() == pri:
                    info = '%8d  ' % int(tasks[ii].get_name())
                    if tasks[ii].get_state() == DELETED:
                        info += '%1.1s  ' % 'D'
                    else:
                        info += '%1.1s  ' % tasks[ii].get_state()[0:1]
                    info += '%7.7s  ' % tasks[ii].get_project()
                    if tasks[ii].note_count() > 0:
                        info += '[%.2d]  ' % tasks[ii].note_count()
                    else:
                        info += '      '
                    info += '%1s  ' % tasks[ii].get_priority()
                    info += '%s' % tasks[ii].get_task()
                    clist.append(info)

    fullpath = os.path.join(dbs_repo(), OPEN)
    tasks.clear()
    for (dirpath, dirnames, filenames) in os.walk(fullpath):
        for ii in filenames:
           file_time = os.path.getmtime(os.path.join(fullpath, ii))

           if current_time - file_time < elapsed_time:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               tasks[ii] = t

    clist.append("")
    if len(tasks) < 1:
        clist.append("No %s tasks touched." % OPEN)
    else:
        if int(days) == 1:
            clist.append("Open tasks touched during the last day:")
        else:
            clist.append("Open tasks touched over the last %d days:" % int(days))
        for pri in [HIGH, MEDIUM, LOW]:
            for ii in sorted(tasks):
               if tasks[ii].get_priority() == pri:
                    info = '%8d  ' % int(tasks[ii].get_name())
                    if tasks[ii].get_state() == DELETED:
                        info += '%1.1s  ' % 'D'
                    else:
                        info += '%1.1s  ' % tasks[ii].get_state()[0:1]
                    info += '%7.7s  ' % tasks[ii].get_project()
                    if tasks[ii].note_count() > 0:
                        info += '[%.2d]  ' % tasks[ii].note_count()
                    else:
                        info += '      '
                    info += '%1s  ' % tasks[ii].get_priority()
                    info += '%s' % tasks[ii].get_task()
                    clist.append(info)

    return clist

#-- main

#-- task help messages
def help_a():
    return ('TASK', 'a', "Add a new task")
    
def help_A():
    return ('TASK', 'A', "Mark a task active")
    
def help_d():
    return ('TASK', 'd', "Mark a task done")
    
def help_e():
    return ('TASK', 'e', "Edit the current task")

def help_I():
    return ('TASK', 'I', "Mark a task inactive (and leave as open)")
    
def help_l():
    return ('TASK', 'l', "Log a task")

def help_minus():
    return ('TASK', '-', "Lower the priority of a task")
    
def help_n():
    return ('TASK', 'n', "Add a note to the current task")

def help_plus():
    return ('TASK', '+', "Raise the priority of a task")
    
def help_r():
    return ('TASK', 'r', "Recap tasks done or touched")
    
def help_s():
    return ('TASK', 's', "Show the current task")

#-- list help messages
def help_ctrl_l_a():
    return ('LIST', 'ctrl-L a', "List all active tasks")

def help_ctrl_l_A():
    return ('LIST', 'ctrl-L A', "List ALL tasks, in any state")

def help_ctrl_l_d():
    return ('LIST', 'ctrl-L d', "List all done tasks")

def help_ctrl_l_D():
    return ('LIST', 'ctrl-L D', "List all deleted tasks")

def help_ctrl_l_o():
    return ('LIST', 'ctrl-L o', "List all open tasks")

def help_ctrl_l_s():
    return ('LIST', 'ctrl-L s', "List project state counts")

#-- motion help messages
def help_j():
    return ('MOVE', 'j, <down arrow>', "Next line")

def help_k():
    return ('MOVE', 'k, <up arrow>', "Previous line")

def help_N():
    return ('MOVE', 'Ctrl-N', "Next project")

def help_P():
    return ('MOVE', 'Ctrl-P', "Previous project")

def help_KEY_DOWN():
    return ('MOVE', '<down arrow>, j', "Next line")

def help_KEY_UP():
    return ('MOVE', '<up arrow>, k', "Previous line")

def help_PAGE_DOWN():
    return ('MOVE', '<PgDn>', "Next page")

def help_PAGE_UP():
    return ('MOVE', '<PgUp>', "Previous page")

#-- miscellaneous help messages
def help_R():
    return ('MISC', 'ctrl-R', "Refresh all project and task info")

def help_v():
    return ('MISC', 'v', "Display the dbs version number")

def help_help():
    return ('MISC', '?', "Help (show this list)")
    
#-- helper functions
def basic_counts():
    global ALL_TASKS, ALL_PROJECTS

    tasks = 0
    projects = 0
    active = 0
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_state() == ACTIVE:
            active += 1
        if t.get_state() != DELETED:
            tasks += 1

    for ii in ALL_PROJECTS:
        p = ALL_PROJECTS[ii]
        if p[ACTIVE] + p[OPEN] > 0:
            projects += 1

    return (projects, active, tasks)

def build_task_info():
    global ALL_TASKS, ALL_PROJECTS
    global ACTIVE_PROJECTS
    global current_task, current_project

    ALL_TASKS.clear()
    ALL_PROJECTS.clear()
    ACTIVE_PROJECTS.clear()

    # get every known task
    for state in dbs_task.ALLOWED_STATES:
        fullpath = os.path.join(dbs_repo(), state)
        for (dirpath, dirnames, filenames) in os.walk(fullpath):
            for ii in filenames:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               if t.get_name() not in ALL_TASKS:
                   ALL_TASKS[t.get_name()] = t
                   proj = t.get_project()
                   if proj not in ALL_PROJECTS:
                       ALL_PROJECTS[proj] = { HIGH:0, MEDIUM:0, LOW:0, \
                                             ACTIVE:0, OPEN:0, DONE:0,
                                             DELETED:0 }
                   pri = t.get_priority()
                   ALL_PROJECTS[proj][pri] += 1
                   s = t.get_state()
                   ALL_PROJECTS[proj][s] += 1

    # isolate the projects with actual activity
    for ii in ALL_PROJECTS:
        p = ALL_PROJECTS[ii]
        if p[ACTIVE] + p[OPEN] > 0:
            if ii not in ACTIVE_PROJECTS:
                ACTIVE_PROJECTS[ii] = { ACTIVE:p[ACTIVE], OPEN:p[OPEN],
                                        HIGH:[], MEDIUM:[], LOW:[] }
    if current_project not in ALL_PROJECTS:
        current_project = ''

    # attach the active tasks to the active projects, by priority
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_project() not in ACTIVE_PROJECTS:
            continue
        s = t.get_state()
        if s == ACTIVE or s == OPEN:
            ACTIVE_PROJECTS[t.get_project()][t.get_priority()].append(t)
        else:
            continue
    if current_task not in ALL_TASKS:
        current_task = ''

    return

def build_text_attrs():
    global WHITE_ON_BLUE, BOLD_WHITE_ON_BLUE
    global PLAIN_TEXT, BOLD_PLAIN_TEXT
    global WHITE_ON_RED, BOLD_WHITE_ON_RED
    global GREEN_ON_BLACK, BOLD_GREEN_ON_BLACK
    global BLUE_ON_BLACK, BOLD_BLUE_ON_BLACK
    global RED_ON_BLACK, BOLD_RED_ON_BLACK

    # color pair 1: blue background, white text
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
    WHITE_ON_BLUE = curses.color_pair(1)
    BOLD_WHITE_ON_BLUE = curses.color_pair(1) | curses.A_BOLD

    # color pair 2: black background, white text
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    PLAIN_TEXT = curses.color_pair(2)
    BOLD_PLAIN_TEXT = PLAIN_TEXT | curses.A_BOLD

    # color pair 3: red background, white text
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_RED)
    WHITE_ON_RED = curses.color_pair(3)
    BOLD_WHITE_ON_RED = curses.color_pair(3) | curses.A_BOLD

    # color pair 4: black background, green text
    curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)
    GREEN_ON_BLACK = curses.color_pair(4)
    BOLD_GREEN_ON_BLACK = curses.color_pair(4) | curses.A_BOLD

    # color pair 5: black background, blue text
    curses.init_pair(5, curses.COLOR_BLUE, curses.COLOR_BLACK)
    BLUE_ON_BLACK = curses.color_pair(5)
    BOLD_BLUE_ON_BLACK = curses.color_pair(5) | curses.A_BOLD

    # color pair 6: black background, red text
    curses.init_pair(6, curses.COLOR_RED, curses.COLOR_BLACK)
    RED_ON_BLACK = curses.color_pair(6)
    BOLD_RED_ON_BLACK = curses.color_pair(6) | curses.A_BOLD

    return

def refresh_header(screen, win, options):
    (sheight, swidth) = screen.getmaxyx()
    blanks = ''.ljust(swidth-1, ' ')
    win.clear()
    win.addstr(0, 0, blanks, BOLD_WHITE_ON_BLUE)
    win.addstr(0, 0, options[0:swidth-1], BOLD_WHITE_ON_BLUE)
    return

def refresh_trailer(screen, win, msg):
    (height, width) = win.getmaxyx()
    dashes = ''.ljust(width-1, '-')
    win.clear()
    win.addstr(0, 0, dashes, BOLD_WHITE_ON_BLUE)
    if msg:
        win.addstr(0, 3, msg, BOLD_WHITE_ON_BLUE)
    else:
        (project_count, active_count, task_count) = basic_counts()
        win.addstr(0, 3, " dbs: %d projects, %d tasks, %d active " %
                (project_count, task_count, active_count), BOLD_WHITE_ON_BLUE)
        vers = ' v' + dbs_task.VERSION + ' '
        win.addstr(0, width-len(vers)-4, vers, BOLD_WHITE_ON_BLUE)
    return

def add_task_note(note):
    global ACTIVE_TASKS, current_task

    task_name = dbs_task.task_canonical_name(current_task)
    t = ACTIVE_TASKS[task_name]
    t.add_note(note)
    t.write(True)
    return

def refresh_cli(screen, win, msg):
    maxy, maxx = win.getmaxyx()
    if len(msg) > 0:
        prefix = msg.split(':')
        if prefix[0] == 'Add note':
            win.addstr(0, 0, prefix[0]+': ', BOLD_RED_ON_BLACK)
            win.addstr(0, len(prefix[0])+1, ' '.join(prefix[1:]), PLAIN_TEXT)
        else:
            win.addstr(0, 0, msg, BOLD_RED_ON_BLACK)
    return

def refresh_projects(screen, win, lines):
    global current_project
    global DBG

    if not current_project:
        current_project = ACTIVE_PROJECTS[0]

    maxy, maxx = win.getmaxyx()
    blanks = ''.ljust(maxx-1, ' ')
    linenum = 0
    for ii in lines:
        info = ii.split('\t')
        pname = info[0]
        attrs = PLAIN_TEXT
        if len(info) > 1:
            attrs = BOLD_WHITE_ON_BLUE
        if pname == current_project:
            attrs = BOLD_WHITE_ON_RED
        win.addstr(linenum, 0, blanks, attrs)
        win.addstr(linenum, 0, ii, attrs)
        win.addch(linenum, PROJECT_WIDTH-1, "|", BOLD_BLUE_ON_BLACK)
        # DBG.write('refresh_projects: ' + str(linenum))
        linenum += 1
        if linenum >= maxy - 1:
            return

    while linenum < maxy-1:
        win.addch(linenum, PROJECT_WIDTH-1, "|", BOLD_BLUE_ON_BLACK)
        linenum += 1

    return

def get_current_task_list(project):
    global ACTIVE_PROJECTS, ALL_TASKS, ACTIVE_TASKS
    global current_task, current_project
    global DBG

    DBG.write('get_current_task_list: ' + project)
    ACTIVE_TASKS.clear()

    if not ALL_TASKS or not ACTIVE_PROJECTS:
        return

    if project not in ACTIVE_PROJECTS:
        current_task = ''
        current_project = ''
        return

    task_list = []
    task_list = ACTIVE_PROJECTS[project][HIGH] + \
                ACTIVE_PROJECTS[project][MEDIUM] + \
                ACTIVE_PROJECTS[project][LOW]
    for ii in task_list:
        t = ALL_TASKS[ii.get_name()]
        if t.get_name() not in ACTIVE_TASKS and t.get_state() != DELETED:
            ACTIVE_TASKS[t.get_name()] = ii

    tlist = sorted(ACTIVE_TASKS.keys())
    if len(tlist) > 0:
        current_task = tlist[0]

    return tlist

def refresh_tasks(screen, win, lines):
    global ACTIVE_TASKS, current_task

    if not current_task:
        return

    maxy, maxx = win.getmaxyx()
    blanks = ''.ljust(maxx-1, ' ')
    linenum = 0
    for ii in lines:
        info = ii.split('\t')
        tname = info[0]
        attrs = PLAIN_TEXT
        pri = info[2]
        if pri == HIGH:
            attrs = BOLD_RED_ON_BLACK
        elif pri == MEDIUM:
            attrs = BOLD_GREEN_ON_BLACK
        if tname in ACTIVE_TASKS:
            if ACTIVE_TASKS[tname].get_state() == ACTIVE:
                attrs = BOLD_WHITE_ON_BLUE
        if tname == current_task:
            attrs = BOLD_WHITE_ON_RED
        txt = "%8d  %4s  %1s  %s" % (int(info[0]), info[1], info[2], info[3])
        win.addstr(linenum, 0, blanks, attrs)
        win.addstr(linenum, 0, txt[0:maxx-1], attrs)
        # DBG.write('refresh_tasks: <' + str(linenum) + '> ' + txt[0:maxx-1])
        linenum += 1
        if linenum >= maxy - 1:
            return

    return

def refresh_list(screen, win, lines):
    global current_line

    maxy, maxx = win.getmaxyx()
    blanks = ''.ljust(maxx-1, ' ')
    linenum = 0
    for ii in lines:
        attrs = PLAIN_TEXT
        win.addstr(linenum, 0, blanks, attrs)
        if ii == current_line:
            attrs = BOLD_PLAIN_TEXT
        win.addstr(linenum, 0, ii[0:maxx-1], attrs)
        # DBG.write('refresh_list: <' + str(linenum) + '> ' + ii)
        linenum += 1
        if linenum >= maxy - 1:
            return

    return

def refresh_help():
    CMDLIST = []
    for ii in globals().keys():
        if HELP_PREFIX.search(str(ii)):
            if str(ii) == 'help_cb':
                continue
            CMDLIST.append(str(ii))
    cmds = sorted(CMDLIST)

    gnames = ['MOVE', 'MISC', 'LIST', 'TASK']
    groups = { 'MOVE':['--- Motion ---',],
               'MISC':['--- Miscellaneous ---',],
               'LIST':['--- Lists (ctrl-L-?) ---',],
               'TASK':['--- Tasks ---',],
             }
    for ii in sorted(cmds):
        (group, key, info) = globals()[ii]()
        info = '%-15s   %s' % (key, info)
        if group not in gnames:
            continue
        groups[group].append(info)

    clines = []
    for ii in ['MOVE', 'TASK', 'LIST', 'MISC']:
        clines.append(groups[ii][0])
        for jj in sorted(groups[ii][1:]):
            clines.append(jj)
        if ii != 'MISC':
            clines.append('')

    return clines

def refresh_active_task_list():
    global ALL_TASKS, current_project

    task_list = collections.OrderedDict()
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_state() == ACTIVE:
            if t.get_name() not in task_list:
                task_list[t.get_name()] = t

    tlines = []
    for ii in sorted(task_list):
        t = task_list[ii]
        info = '%8d  ' % int(t.get_name())
        info += '%7.7s  ' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]  ' % t.note_count()
        else:
            info += '       '
        info += '%1s  ' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    return sorted(tlines)

def refresh_done_task_list():
    global ALL_TASKS, current_project

    task_list = collections.OrderedDict()
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_state() == DONE:
            if t.get_name() not in task_list:
                task_list[t.get_name()] = t

    tlines = []
    for ii in sorted(task_list):
        t = task_list[ii]
        info = '%8d  ' % int(t.get_name())
        info += '%7.7s  ' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]  ' % t.note_count()
        else:
            info += '      '
        info += '%1s  ' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    return sorted(tlines)

def all_cb(win, maxx, linenum, line):
    info = line.split('\t')
    if len(info) < 1:
        return
    if info[3] == HIGH:
        hi_attr = BOLD_RED_ON_BLACK
        low_attr = BOLD_RED_ON_BLACK
    elif info[3] == MEDIUM:
        hi_attr = BOLD_GREEN_ON_BLACK
        low_attr = GREEN_ON_BLACK
    elif info[3] == LOW:
        hi_attr = BOLD_PLAIN_TEXT
        low_attr = PLAIN_TEXT
    win.addstr(linenum, 0, info[0], hi_attr)
    win.addstr(linenum, 5, info[1], low_attr)
    win.addstr(linenum, 13, info[2], low_attr)
    win.addstr(linenum, 18, info[3], hi_attr)
    win.addstr(linenum, 20, ' '.join(info[4:])[0:maxx-20], low_attr)
    return

def all_with_state_cb(win, maxx, linenum, line):
    info = line.split('\t')
    if len(info) < 1:
        return
    if info[4] == HIGH:
        hi_attr = BOLD_RED_ON_BLACK
        low_attr = BOLD_RED_ON_BLACK
    elif info[4] == MEDIUM:
        hi_attr = BOLD_GREEN_ON_BLACK
        low_attr = GREEN_ON_BLACK
    elif info[4] == LOW:
        hi_attr = BOLD_PLAIN_TEXT
        low_attr = PLAIN_TEXT
    win.addstr(linenum, 0, info[0], hi_attr)
    win.addstr(linenum, 5, info[1], low_attr)
    win.addstr(linenum, 7, info[2], low_attr)
    win.addstr(linenum, 15, info[3], low_attr)
    win.addstr(linenum, 20, info[4], hi_attr)
    win.addstr(linenum, 22, ' '.join(info[5:])[0:maxx-22], low_attr)
    return

def refresh_all_tasks():
    global ALL_TASKS

    tlines = []
    for ii in sorted(ALL_TASKS):
        t = ALL_TASKS[ii]
        info = '%8d  ' % int(t.get_name())
        if t.get_state() == DELETED:
            info += '%1.1s  ' % 'D'
        else:
            info += '%1.1s  ' % t.get_state()[0:1]
        info += '%7.7s  ' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]  ' % t.note_count()
        else:
            info += '      '
        info += '%1s  ' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    return sorted(tlines)

def refresh_deleted_tasks():
    global ALL_TASKS

    task_list = collections.OrderedDict()
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_state() == DELETED:
            if t.get_name() not in task_list:
                task_list[t.get_name()] = t

    tlines = []
    for ii in sorted(task_list):
        t = task_list[ii]
        info = '%8d  ' % int(t.get_name())
        info += '%7.7s  ' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]  ' % t.note_count()
        else:
            info += '      '
        info += '%1s  ' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    return sorted(tlines)

def refresh_open_tasks():
    global ALL_TASKS

    task_list = collections.OrderedDict()
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_state() == OPEN:
            if t.get_name() not in task_list:
                task_list[t.get_name()] = t

    tlines = []
    for ii in sorted(task_list):
        t = task_list[ii]
        info = '%8d  ' % int(t.get_name())
        info += '%7.7s  ' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]  ' % t.note_count()
        else:
            info += '      '
        info += '%1s  ' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    return sorted(tlines)

def refresh_state_counts():
    global ALL_TASKS

    projects = collections.OrderedDict()
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_project() not in projects:
            projects[t.get_project()] = { ACTIVE:0, OPEN:0,
                                          DONE:0, DELETED:0 }
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        projects[t.get_project()][t.get_state()] += 1

    tlines = []
    for ii in sorted(projects):
        info  = '{: <8}'.format(ii[0:8])
        info += '  %4d' % projects[ii][ACTIVE]
        info += '   %4d' % projects[ii][OPEN]
        info += '  %4d' % projects[ii][DONE]
        info += '    %4d' % projects[ii][DELETED]
        total = 0
        for jj in projects[ii]:
            total += projects[ii][jj]
        info += '    %4d' % total
        tlines.append(info)

    return sorted(tlines)

def edit_task(raw_name):
    global DBG, ALL_TASKS

    ret = ''
    task_name = dbs_task.task_canonical_name(raw_name)
    t = ALL_TASKS[task_name]
    DBG.write('edit_task: %s' % task_name)

    # copy the file to a temporary location
    before_edit = t.show_text()
    tfd, tpath = tempfile.mkstemp(text=True)
    before = bytearray()
    before.extend(before_edit.encode("utf-8"))
    os.write(tfd, before)
    os.fsync(tfd)

    # pop the editor onto the screen
    editor = os.environ['EDITOR']
    if not editor:
        editor = 'vi'
    result = subprocess.run([editor, tpath])
    os.lseek(tfd, 0, 0)
    after = os.read(tfd, os.fstat(tfd).st_size)
    os.close(tfd)
    try:
        os.remove(tpath)
    except OSError:
        pass

    # verify the task content
    after_edit = after.decode("utf-8").split('\n')[0:-1]
    DBG.write('edit_task: new text is:\n%s' % (after_edit))
    ret = t.validate(after_edit)
    # report an error if needed
    if len(ret) == 0:
        if before_edit == after_edit:
            ret = 'edit: no changes made'
        else:
            old_state = t.get_state()
            t.set_fields(after_edit)
            t.add_note('edited')
            dbs_task.put_task(t, True)

    DBG.write('edit_task: %s (was, now) = %d, %d [%s]' %
              (task_name, len(before_edit), len(after_edit), ret))
    return ret

def refresh_show():
    global ALL_TASKS, current_task

    t = ALL_TASKS[current_task]
    tlines = []
    tlines.append('Name: %s' % t.get_name())
    tlines.append('Task: %s' % t.get_task())
    tlines.append('State: %s' % t.get_state())
    tlines.append('Project: %s' % t.get_project())
    tlines.append('Priority: %s' % t.get_priority())
    for ii in t.get_notes():
        tlines.append('Note: %s' % ii)
    return tlines

def build_windows(screen):
    global DBG

    windows = {}
    panels = {}

    screen.clear()

    # how big is the screen?
    maxy, maxx = screen.getmaxyx()
    DBG.write('build: maxy, maxx: %d, %d' % (maxy, maxx))

    # create project list: 1/4, left of screen
    key = PROJ_PANEL
    main_height = maxy - 3
    prj_width = PROJECT_WIDTH
    windows[key] = screen.subwin(main_height, prj_width, 1, 0)
    panels[key] = curses.panel.new_panel(windows[key])
    DBG.write('prj: h,w,y,x: %d, %d, %d, %d' % (main_height, prj_width, 1, 0))

    # create task list: 3/4, right of screen
    key = TASK_PANEL
    tsk_width = maxx - prj_width
    windows[key] = screen.subwin(main_height, tsk_width, 1, prj_width)
    panels[key] = curses.panel.new_panel(windows[key])
    DBG.write('tsk: h,w,y,x: %d, %d, %d, %d' % (main_height, tsk_width, 1, prj_width))

    # create a generic list panel to be re-used for all sorts of things
    # (help, show and done, for example)
    main_height = maxy - 3
    for ii in [LIST_PANEL]:
        windows[ii] = screen.subwin(main_height, maxx, 1, 0)
        panels[ii] = curses.panel.new_panel(windows[ii])
        DBG.write('%s: h,w,y,x: %d, %d, %d, %d' % (ii, main_height, maxx, 1, 0))

    DBG.write('end build')
    return (windows, panels)

def resize_windows(stdscr, windows):
    curses.curs_set(0)
    stdscr.clear()
    for ii in windows.keys():
        windows[ii].resize(stdscr)
    return

def dbsui(stdscr):
    global DBG, current_project, current_task, current_line

    windows = {}
    curses.curs_set(0)
    stdscr.clear()
    maxy, maxx = stdscr.getmaxyx()
    ret = ''

    # initialize global items
    build_task_info()
    build_text_attrs()

    # build up all of the windows and panels
    windows[HEADER_PANEL] = DbsHeader(HEADER_PANEL, stdscr, refresh_header)
    windows[TRAILER_PANEL] = DbsTrailer(TRAILER_PANEL, stdscr, refresh_trailer)
    windows[CLI_PANEL] = DbsCli(CLI_PANEL, stdscr, refresh_cli)
    windows[PROJ_PANEL] = DbsProjects(PROJ_PANEL, stdscr, refresh_projects)
    windows[TASK_PANEL] = DbsTasks(TASK_PANEL, stdscr, refresh_tasks)
    windows[LIST_PANEL] = DbsList(LIST_PANEL, stdscr, refresh_list)

    state = 0
    windows[HEADER_PANEL].set_text(MAIN_HEADER, '')
    while True:
        stdscr.clear()
        maxy, maxx = stdscr.getmaxyx()

        DBG.write('state: %d' % (state))
        windows[HEADER_PANEL].refresh()
        windows[TRAILER_PANEL].refresh()
        if len(ret) > 0:
            DBG.write('cli: ' + ret)
        windows[CLI_PANEL].refresh()
        windows[PROJ_PANEL].refresh()
        windows[TASK_PANEL].refresh()

        if state != 0:
            windows[LIST_PANEL].refresh()
        windows[CLI_PANEL].set_text('')

        curses.panel.update_panels()
        stdscr.refresh()
        key = stdscr.getkey()
        DBG.write('main: getkey "%s"' % key)

        if state == 0:
            if key == 'q' or key == curses.KEY_EXIT:
                break

            elif key == '?':
                clist = refresh_help()
                if len(clist) > 0:
                    windows[HEADER_PANEL].set_text(HELP_HEADER, '')
                    windows[PROJ_PANEL].hide()
                    windows[TASK_PANEL].hide()
                    windows[LIST_PANEL].set_content(clist)
                    msg = ' help: all commands '
                    windows[TRAILER_PANEL].set_text(msg)
                    windows[LIST_PANEL].show()
                else:
                    msg = '? no help info found'
                    windows[CLI_PANEL].set_text(msg)
                state = 10

            elif key == 'a':
                # replace the screen with an EDITOR session
                raw_task = dbs_task.dbs_next()
                tname = dbs_task.task_canonical_name(raw_task)
                response = add_task(tname)
                if not response:
                    current_task = tname
                    build_task_info()
                    windows[PROJ_PANEL].populate()
                    windows[TASK_PANEL].populate()
                    response = ''
                else:
                    windows[CLI_PANEL].set_text(response)

            elif key == 'A':
                task_name = dbs_task.task_canonical_name(current_task)
                if task_name in ALL_TASKS:
                    msg = 'Mark %d active (y/[n])? ' % int(current_task)
                    response = windows[CLI_PANEL].get_response(msg)
                    if response == 'y' or response == 'Y':
                        mark_active(current_task)
                    elif response == 'n' or response == 'N':
                        pass
                    elif not response:
                        pass
                    else:
                        msg = '? enter y or n, not %s' % response
                        windows[CLI_PANEL].set_text(msg)

                    current_project = ''
                    current_task = ''
                    build_task_info()
                    windows[PROJ_PANEL].populate()
                    windows[TASK_PANEL].populate()
                else:
                    msg = '? no such task found: %d' % int(current_task)
                    windows[CLI_PANEL].set_text(msg)

            elif key == 'd':
                task_name = dbs_task.task_canonical_name(current_task)
                if task_name in ALL_TASKS:
                    msg = 'Mark %d done (y/[n])? ' % int(current_task)
                    response = windows[CLI_PANEL].get_response(msg)
                    if response == 'y' or response == 'Y':
                        mark_done(current_task)
                    elif response == 'n' or response == 'N':
                        pass
                    elif not response:
                        pass
                    else:
                        msg = '? enter y or n, not %s' % response
                        windows[CLI_PANEL].set_text(msg)

                    current_project = ''
                    current_task = ''
                    build_task_info()
                    windows[PROJ_PANEL].populate()
                    windows[TASK_PANEL].populate()
                else:
                    msg = '? no such task found: %d' % int(current_task)
                    windows[CLI_PANEL].set_text(msg)

            elif key == 'D':
                task_name = dbs_task.task_canonical_name(current_task)
                if task_name in ALL_TASKS:
                    msg = 'Delete %d (y/[n])? ' % int(current_task)
                    response = windows[CLI_PANEL].get_response(msg)
                    if response == 'y' or response == 'Y':
                        mark_deleted(current_task)
                    elif response == 'n' or response == 'N':
                        pass
                    elif not response:
                        pass
                    else:
                        msg = '? enter y or n, not %s' % response
                        windows[CLI_PANEL].set_text(msg)

                    current_project = ''
                    current_task = ''
                    build_task_info()
                    windows[PROJ_PANEL].populate()
                    windows[TASK_PANEL].populate()
                else:
                    msg = '? no such task found: %d' % int(current_task)
                    windows[CLI_PANEL].set_text(msg)

            elif key == '-':
                task_name = dbs_task.task_canonical_name(current_task)
                if task_name in ALL_TASKS:
                    msg = 'Move %d priority down (y/[n])? ' % int(current_task)
                    response = windows[CLI_PANEL].get_response(msg)
                    if response == 'y' or response == 'Y':
                        mark_lower(current_task)
                    elif response == 'n' or response == 'N':
                        pass
                    elif not response:
                        pass
                    else:
                        msg = '? enter y or n, not %s' % response
                        windows[CLI_PANEL].set_text(msg)

                    current_project = ''
                    current_task = ''
                    build_task_info()
                    windows[PROJ_PANEL].populate()
                    windows[TASK_PANEL].populate()
                else:
                    msg = '? no such task found: %d' % int(current_task)
                    windows[CLI_PANEL].set_text(msg)

            elif key == 'e':
                # replace the screen with an EDITOR session
                if dbs_task.task_canonical_name(current_task) in ALL_TASKS:
                    prompt = 'Edit [%d]: ' % int(current_task)
                    response = windows[CLI_PANEL].get_response(prompt)
                    if not response:
                        response = current_task
                    ret = edit_task(response)
                    if len(ret) > 0:
                        windows[CLI_PANEL].set_text(ret)
                    else:
                        build_task_info()
                        windows[PROJ_PANEL].populate()
                        windows[TASK_PANEL].populate()
                        response = ''
                else:
                    msg = '? no such task found: %d' % int(current_task)
                    windows[CLI_PANEL].set_text(msg)

            elif key == 'I':
                task_name = dbs_task.task_canonical_name(current_task)
                if task_name in ALL_TASKS:
                    msg = 'Mark %d inactive (y/[n])? ' % int(current_task)
                    response = windows[CLI_PANEL].get_response(msg)
                    if response == 'y' or response == 'Y':
                        mark_inactive(current_task)
                    elif response == 'n' or response == 'N':
                        pass
                    elif not response:
                        pass
                    else:
                        msg = '? enter y or n, not %s' % response
                        windows[CLI_PANEL].set_text(msg)

                    current_project = ''
                    current_task = ''
                    build_task_info()
                    windows[PROJ_PANEL].populate()
                    windows[TASK_PANEL].populate()
                else:
                    msg = '? no such task found: %d' % int(current_task)
                    windows[CLI_PANEL].set_text(msg)

            elif key == 'j' or str(key) == 'KEY_DOWN':
                windows[TASK_PANEL].next_task()

            elif key == 'k' or str(key) == 'KEY_UP':
                windows[TASK_PANEL].prev_task()

            elif key == 'l':
                # replace the screen with an EDITOR session
                raw_task = dbs_task.dbs_next()
                tname = dbs_task.task_canonical_name(raw_task)
                response = log_task(tname)
                if not response:
                    current_taks = tname
                    build_task_info()
                    windows[PROJ_PANEL].populate()
                    windows[TASK_PANEL].populate()
                    response = ''
                else:
                    windows[CLI_PANEL].set_text(response)

            elif key == 'n':
                task_name = dbs_task.task_canonical_name(current_task)
                if task_name in ALL_TASKS:
                    this_task = task_name
                    response = windows[CLI_PANEL].get_response('Add note: ')
                    add_task_note(response)
                    windows[TASK_PANEL].populate()
                    current_task = this_task
                else:
                    msg = '? no such task found: %d' % int(current_task)
                    windows[CLI_PANEL].set_text(msg)

            elif key == 'r':
                days = windows[CLI_PANEL].get_response('Number of days [7]: ')
                if not days:
                    days = 7
                clist = refresh_recap(days)
                if len(clist) > 0:
                    windows[HEADER_PANEL].set_text(RECAP_HEADER, '')
                    windows[PROJ_PANEL].hide()
                    windows[TASK_PANEL].hide()
                    windows[LIST_PANEL].set_content(clist)
                    msg = ' recap: %d day' % int(days)
                    if int(days) > 1:
                        msg += 's'
                    msg += ' '
                    windows[TRAILER_PANEL].set_text(msg)
                    windows[LIST_PANEL].show()
                    state = 10
                else:
                    msg = '? no tasks found'
                    windows[CLI_PANEL].set_text(msg)

            elif key == 's':
                clist = refresh_show()
                if len(clist) > 0:
                    windows[HEADER_PANEL].set_text(SHOW_HEADER, '')
                    windows[PROJ_PANEL].hide()
                    windows[TASK_PANEL].hide()
                    windows[LIST_PANEL].set_content(clist)
                    msg = ' show: task %d ' % int(current_task)
                    windows[TRAILER_PANEL].set_text(msg)
                    windows[LIST_PANEL].show()
                    state = 10
                else:
                    msg = '? no task content found'
                    windows[CLI_PANEL].set_text(msg)

            elif key == '+':
                task_name = dbs_task.task_canonical_name(current_task)
                if task_name in ALL_TASKS:
                    msg = 'Move %d priority up (y/[n])? ' % int(current_task)
                    response = windows[CLI_PANEL].get_response(msg)
                    if response == 'y' or response == 'Y':
                        mark_higher(current_task)
                    elif response == 'n' or response == 'N':
                        pass
                    elif not response:
                        pass
                    else:
                        msg = '? enter y or n, not %s' % response
                        windows[CLI_PANEL].set_text(msg)

                    current_project = ''
                    current_task = ''
                    build_task_info()
                    windows[PROJ_PANEL].populate()
                    windows[TASK_PANEL].populate()
                else:
                    msg = '? no such task found: %d' % int(current_task)
                    windows[CLI_PANEL].set_text(msg)

            elif key == '-':
                task_name = dbs_task.task_canonical_name(current_task)
                if task_name in ALL_TASKS:
                    msg = 'Move %d priority down (y/[n])? ' % int(current_task)
                    response = windows[CLI_PANEL].get_response(msg)
                    if response == 'y' or response == 'Y':
                        mark_lower(current_task)
                    elif response == 'n' or response == 'N':
                        pass
                    elif not response:
                        pass
                    else:
                        msg = '? enter y or n, not %s' % response
                        windows[CLI_PANEL].set_text(msg)

                    current_project = ''
                    current_task = ''
                    build_task_info()
                    windows[PROJ_PANEL].populate()
                    windows[TASK_PANEL].populate()
                else:
                    msg = '? no such task found: %d' % int(current_task)
                    windows[CLI_PANEL].set_text(msg)

            elif key == 'v':
                windows[CLI_PANEL].set_text(VERSION_TEXT)
                state = 0

            # handle all lists here
            elif key == '':
                response = windows[CLI_PANEL].get_response('Which list? ')
                if response == 'a':
                    clist = refresh_active_task_list()
                    if len(clist) > 0:
                        windows[HEADER_PANEL].set_text(TASKS_HEADER,
                                                    '|| Active Tasks ')
                        windows[PROJ_PANEL].hide()
                        windows[TASK_PANEL].hide()
                        windows[LIST_PANEL].set_content(clist)
                        msg = ACTIVE_TASKS_TRAILER % (len(clist))
                        windows[TRAILER_PANEL].set_text(msg)
                        windows[LIST_PANEL].show()
                        state = 20
                    else:
                        msg = '? no active tasks'
                        windows[CLI_PANEL].set_text(msg)

                elif response == 'A':
                    clist = refresh_all_tasks()
                    if len(clist) > 0:
                        windows[HEADER_PANEL].set_text(TASKS_HEADER,
                                                       ' || All Tasks ')
                        windows[PROJ_PANEL].hide()
                        windows[TASK_PANEL].hide()
                        windows[LIST_PANEL].set_content(clist)
                        msg = ALL_TASKS_TRAILER % len(clist)
                        windows[TRAILER_PANEL].set_text(msg)
                        windows[LIST_PANEL].show()
                        state = 20
                    else:
                        msg = '? no tasks found'
                        windows[CLI_PANEL].set_text(msg)

                elif response == 'd':
                    clist = refresh_done_task_list()
                    if len(clist) > 0:
                        windows[HEADER_PANEL].set_text(TASKS_HEADER,
                                                    ' || Done Tasks ')
                        windows[PROJ_PANEL].hide()
                        windows[TASK_PANEL].hide()
                        windows[LIST_PANEL].set_content(clist)
                        msg = ' tasks: %d done ' % (len(clist))
                        windows[TRAILER_PANEL].set_text(msg)
                        windows[LIST_PANEL].show()
                        state = 20
                    else:
                        msg = '? no done tasks'
                        windows[CLI_PANEL].set_text(msg)

                elif response == 'D':
                    clist = refresh_deleted_tasks()
                    if len(clist) > 0:
                        windows[HEADER_PANEL].set_text(TASKS_HEADER,
                                                    ' || Deleted Tasks ')
                        windows[PROJ_PANEL].hide()
                        windows[TASK_PANEL].hide()
                        windows[LIST_PANEL].set_content(clist)
                        msg = DELETED_TASKS_TRAILER % len(clist)
                        windows[TRAILER_PANEL].set_text(msg)
                        windows[LIST_PANEL].show()
                        state = 20
                    else:
                        msg = '? no deleted tasks'
                        windows[CLI_PANEL].set_text(msg)

                elif response == 'o':
                    clist = refresh_open_tasks()
                    if len(clist) > 0:
                        windows[HEADER_PANEL].set_text(TASKS_HEADER,
                                                    ' || Open Tasks ')
                        windows[PROJ_PANEL].hide()
                        windows[TASK_PANEL].hide()
                        windows[LIST_PANEL].set_content(clist)
                        msg = OPEN_TASKS_TRAILER % len(clist)
                        windows[TRAILER_PANEL].set_text(msg)
                        windows[LIST_PANEL].show()
                        state = 20
                    else:
                        msg = '? no open tasks'
                        windows[CLI_PANEL].set_text(msg)

                elif response == 's':
                    windows[HEADER_PANEL].set_text(STATE_COUNTS_HEADER,
                                                '  || State Counts ')
                    windows[PROJ_PANEL].hide()
                    windows[TASK_PANEL].hide()
                    clist = refresh_state_counts()
                    windows[LIST_PANEL].set_content(clist)
                    msg = ' projects: %d ' % (len(clist))
                    windows[TRAILER_PANEL].set_text(msg)
                    windows[LIST_PANEL].show()
                    state = 10

            elif key == '':
                windows[PROJ_PANEL].next_project()
                windows[TASK_PANEL].populate()

            elif key == '':
                windows[PROJ_PANEL].prev_project()
                windows[TASK_PANEL].populate()

            elif key == '':
                current_project = ''
                current_task = ''
                build_task_info()
                windows[PROJ_PANEL].populate()
                windows[TASK_PANEL].populate()

            elif key == 'KEY_RESIZE' or key == curses.KEY_RESIZE:
                if curses.is_term_resized(maxy, maxx):
                    resize_windows(stdscr, windows)
                state = 0

            elif key == '\n':
                state = 0

            elif str(key) == 'KEY_NPAGE':
                windows[TASK_PANEL].next_page()
                state = 0

            elif str(key) == 'KEY_PPAGE':
                windows[TASK_PANEL].prev_page()
                state = 0

            else:
                ret = "? no such command: %s" % str(key)
                windows[CLI_PANEL].set_text(ret)
                state = 0
                
        elif state == 10:
            if key == 'q':
                windows[HEADER_PANEL].set_text(MAIN_HEADER, '')
                windows[TRAILER_PANEL].set_text('')
                windows[LIST_PANEL].hide()
                windows[PROJ_PANEL].show()
                windows[TASK_PANEL].show()
                state = 0
            elif key == 'j' or str(key) == 'KEY_DOWN':
                windows[LIST_PANEL].next()
            elif key == 'k' or str(key) == 'KEY_UP':
                windows[LIST_PANEL].prev()
            elif key == 'KEY_RESIZE' or key == curses.KEY_RESIZE:
                if curses.is_term_resized(maxy, maxx):
                    resize_windows(stdscr, windows)
            elif str(key) == 'KEY_NPAGE':
                windows[LIST_PANEL].next_page()
            elif str(key) == 'KEY_PPAGE':
                windows[LIST_PANEL].prev_page()
            else:
                ret = "? no such command: %s" % str(key)
                windows[CLI_PANEL].set_text(ret)
                state = 10

        elif state == 20:
            if key == 'q':
                windows[HEADER_PANEL].set_text(MAIN_HEADER, '')
                windows[TRAILER_PANEL].set_text('')
                windows[LIST_PANEL].hide()
                windows[PROJ_PANEL].show()
                windows[TASK_PANEL].show()
                state = 0
            elif key == 'e':
                # replace the screen with and EDITOR session
                tname = current_line.split()[0]
                prompt = 'Edit [%s]: ' % tname
                response = windows[CLI_PANEL].get_response(prompt)
                if not response:
                    response = tname
                ret = edit_task(response)
                if len(ret) > 0:
                    windows[CLI_PANEL].set_text(ret)
                else:
                    build_task_info()
                    windows[PROJ_PANEL].populate()
                    windows[TASK_PANEL].populate()
                response = ''
            elif key == 'j' or str(key) == 'KEY_DOWN':
                windows[LIST_PANEL].next()
            elif key == 'k' or str(key) == 'KEY_UP':
                windows[LIST_PANEL].prev()
            elif key == 'KEY_RESIZE' or key == curses.KEY_RESIZE:
                if curses.is_term_resized(maxy, maxx):
                    resize_windows(stdscr, windows)
            elif str(key) == 'KEY_NPAGE':
                windows[LIST_PANEL].next_page()
            elif str(key) == 'KEY_PPAGE':
                windows[LIST_PANEL].prev_page()
            elif key == 's':
                prev_task = current_task
                tname = current_line.split()[0]
                current_task = dbs_task.task_canonical_name(tname)
                windows[HEADER_PANEL].save_previous()
                windows[PROJ_PANEL].save_previous()
                windows[TASK_PANEL].save_previous()
                windows[LIST_PANEL].save_previous()
                windows[TRAILER_PANEL].save_previous()
                new_clist = refresh_show()
                if len(new_clist) > 0:
                    windows[HEADER_PANEL].set_text(SHOW_HEADER, '')
                    windows[PROJ_PANEL].hide()
                    windows[TASK_PANEL].hide()
                    windows[LIST_PANEL].set_content(new_clist)
                    msg = ' show: task %d ' % int(current_task)
                    windows[TRAILER_PANEL].set_text(msg)
                    windows[LIST_PANEL].show()
                    state = 30
                else:
                    msg = '? no task content found'
                    windows[CLI_PANEL].set_text(msg)
            else:
                ret = "? no such command: %s" % str(key)
                windows[CLI_PANEL].set_text(ret)
                state = 20

        elif state == 30:
            if key == 'q':
                current_task = dbs_task.task_canonical_name(prev_task)
                windows[HEADER_PANEL].restore_previous()
                windows[PROJ_PANEL].restore_previous()
                windows[TASK_PANEL].restore_previous()
                windows[LIST_PANEL].restore_previous()
                windows[TRAILER_PANEL].restore_previous()
                state = 20
            elif key == 'j' or str(key) == 'KEY_DOWN':
                windows[LIST_PANEL].next()
            elif key == 'k' or str(key) == 'KEY_UP':
                windows[LIST_PANEL].prev()
            elif key == 'KEY_RESIZE' or key == curses.KEY_RESIZE:
                if curses.is_term_resized(maxy, maxx):
                    resize_windows(stdscr, windows)
            elif str(key) == 'KEY_NPAGE':
                windows[LIST_PANEL].next_page()
            elif str(key) == 'KEY_PPAGE':
                windows[LIST_PANEL].prev_page()
            else:
                ret = "? no such command: %s" % str(key)
                windows[CLI_PANEL].set_text(ret)
                state = 30

    return

#-- link to main
def dbsui_main():
    global DBG

    #-- create the "data base"
    if not os.path.isfile(dbs_task.dbs_config_name()):
        dbs_task.dbs_defconfig()
    dbs_task.dbs_read_config()

    if not os.path.isdir(dbs_task.dbs_repo()):
        dbs_task.dbs_make_repo()

    if not dbs_task.dbs_data_dirs_exist():
        dbs_task.dbs_make_data_dirs()

    #-- start up the UI
    DBG = Debug()
    curses.wrapper(dbsui)
    DBG.done()

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

ERROR_MODE = 'error'
MAIN_MODE = 'main'
HELP_MODE = 'help'
TASK_LIST_MODE = 'task_list'
VERSION_MODE = 'version'

CLI_PANEL     = 'cli'
HEADER_PANEL  = 'hdr'
LIST_PANEL    = 'lst'
PROJ_PANEL    = 'prj'
TASK_PANEL    = 'tsk'
TRAILER_PANEL = 'trlr'

MAIN_OPTIONS         = 'DBS || q: Quit   o: Open   ?: Help'
HELP_OPTIONS         = 'Help || j: NextLine   k: PrevLine   q: Quit'
TASK_LIST_OPTIONS    = 'Tasks || j: NextLine   k: PrevLine   q: Quit'
VERSION_OPTIONS      = 'dbsui, v' + dbs_task.VERSION + ' '

DBG = None
PROJECT_WIDTH = 20

#-- classes
class DbsPanel:
    def __init__(self, name, screen, content_cb):
        # basic initialization
        self.name = name
        self.current_index = 0
        self.current_line = 0
        self.current_page = 0
        self.page_height = 0

        self.content_cb = content_cb
        self.content = []

        self.mode = MAIN_MODE
        self.modes = { MAIN_MODE: '',
                       HELP_MODE: '',
                       VERSION_MODE: '',
                       ERROR_MODE: '',
                       TASK_LIST_MODE: '',
                     }

        self.screen = screen
        self.window = None
        self.panel = None
        self.hidden = False
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

    def refresh(self, mode):
        # refresh the window content -- needs replacing for each panel type
        print("refresh not implemented")
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

        # go to next line of content
        self.current_index += 1
        if self.current_index > len(self.content) - 1:
            self.current_index = len(self.content) - 1

        # move down one line, page if needed
        last_line = ((self.current_page + 1) * self.page_height) - 1
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

        # go to previous line of content
        self.current_index -= 1
        if self.current_index < 0:
            self.current_index = 0

        # move up one line, page if needed
        first_line = (self.current_page * self.page_height) - 1
        if self.current_index < first_line:
            self.current_page -= 1
        if self.current_page < 0:
            self.current_page = 0

        DBG.write('prev: index %d, page %d, height %d' %
                  (self.current_index, self.current_page, self.page_height))
        return

    def set_mode(self, mode, text = ''):
        self.mode = mode
        if text:
            self.modes[mode] = text
        return

    def get_mode(self):
        return self.mode
    
    def resize(self, screen):
        del self.panel
        del self.window
        self.screen = screen
        self.create()
        return

class DbsHeader(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsHeader, self).__init__(name, screen, content_cb)
        self.modes = { MAIN_MODE: MAIN_OPTIONS,
                       HELP_MODE: HELP_OPTIONS,
                       VERSION_MODE: MAIN_OPTIONS,
                       ERROR_MODE: MAIN_OPTIONS,
                       TASK_LIST_MODE: TASK_LIST_OPTIONS,
                     }
        self.create()
        return

    def create(self):
        maxy, maxx = self.screen.getmaxyx()
        super(DbsHeader, self).create_win(1, maxx, 0, 0)
        return

    def hide(self):
        # disabled for this panel
        return

    def show(self):
        # disabled for this panel
        return

    def refresh(self, mode):
        self.mode = mode
        self.content_cb(self.screen, self.window, self.modes[self.mode])
        DBG.write('DbsHeader.refresh: mode, msg = %s, "%s"' %
                  (self.mode, self.modes[self.mode]))
        return


class DbsTrailer(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsTrailer, self).__init__(name, screen, content_cb)
        self.mode = MAIN_MODE
        self.create()
        return

    def create(self):
        maxy, maxx = self.screen.getmaxyx()
        super(DbsTrailer, self).create_win(1, maxx, maxy-2, 0)
        return

    def refresh(self, mode):
        self.mode = mode
        self.content_cb(self.screen, self.window, self.modes[self.mode])
        return

    def hide(self):
        # disabled for this panel
        return

    def show(self):
        # disabled for this panel
        return


class DbsCli(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsCli, self).__init__(name, screen, content_cb)
        self.mode = MAIN_MODE
        self.set_mode(VERSION_MODE, VERSION_OPTIONS)
        self.create()
        return

    def create(self):
        maxy, maxx = self.screen.getmaxyx()
        super(DbsCli, self).create_win(1, maxx, maxy-1, 0)
        return

    def refresh(self, mode):
        self.mode = mode
        self.content_cb(self.screen, self.window, self.modes[self.mode])
        return

    def hide(self):
        # disabled for this panel
        return

    def show(self):
        # disabled for this panel
        return


class DbsProjects(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsProjects, self).__init__(name, screen, content_cb)
        self.mode = MAIN_MODE
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

    def refresh(self, mode):
        global current_project, current_task
        global DBG

        if self.hidden:
            return

        self.mode = mode
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

        self.next()
        self.current_project = self.content[self.current_index].split('\t')[0]
        current_project = self.current_project

        return

    def prev_project(self):
        global current_project

        self.prev()
        self.current_project = self.content[self.current_index].split('\t')[0]
        current_project = self.current_project

        return


class DbsTasks(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsTasks, self).__init__(name, screen, content_cb)
        self.mode = MAIN_MODE
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

    def refresh(self, mode):
        global current_task
        global DBG

        if self.hidden:
            self.current_index = 0
            self.current_page = 0
            current_task = self.content[self.current_index].split('\t')[0]
            return

        self.mode = mode
        start = self.current_page * (self.page_height - 1)
        plist = self.content[start:]
        DBG.write('DbsTasks::refresh: first, last, height = %d, %d, %d' %
                  (start, len(self.content)-1, self.page_height))
        self.content_cb(self.screen, self.window, plist)
        return

    def populate(self):
        global ACTIVE_TASKS, current_project, current_task

        tlist = get_current_task_list(current_project)
        clist = []
        for ii in tlist:
            t = ACTIVE_TASKS[ii]
            info = '%4.4s' % t.get_name()
            if t.note_count() > 0:
                info += '\t[%2d]' % t.note_count()
            else:
                info += '\t    '
            info += '\t%s' % t.get_priority()
            info += '\t%s' % t.get_task()
            if t.get_state() == ACTIVE:
                info += '\tACTIVE'
            clist.append(info)

        self.content = sorted(clist)
        if len(self.content) > 0:
            self.current_task = self.content[0].split('\t')[0]
        current_task = self.current_task
        self.current_index = 0
        self.current_page = 0
        return

    def next_task(self):
        global current_task

        self.next()
        self.current_task = self.content[self.current_index].split('\t')[0]
        current_task = self.current_task

        return

    def prev_task(self):
        global current_task

        self.prev()
        self.current_task = self.content[self.current_index].split('\t')[0]
        current_task = self.current_task

        return


class DbsList(DbsPanel):
    def __init__(self, name, screen, content_cb):
        super(DbsList, self).__init__(name, screen, content_cb)
        self.mode = MAIN_MODE
        self.set_mode(HELP_MODE, HELP_OPTIONS)
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

    def refresh(self, mode):
        global current_project
        global DBG

        if mode not in [HELP_MODE]:
            self.current_index = 0
            self.current_page = 0
            return

        self.mode = mode
        start = self.current_page * (self.page_height - 1)
        plist = self.content[start:]
        DBG.write('DbsList::refresh: "%s", first, last = %d, %d' %
                  (self.mode, start, len(self.content)-1))
        self.content_cb(self.screen, self.window, plist)
        return

    def set_content(self, clist):
        global DBG, current_line

        self.window.clear()
        self.content = sorted(clist)
        self.current_index = 0
        self.current_page = 0
        current_line = self.content[self.current_index]
        #DBG.write('set_content: line = "%s"' % current_line)
        #DBG.write('set_content: content\n%s' % '\n'.join(self.content))
        return

    def populate(self):
        return

    def next_line(self):
        global current_line

        self.next()
        current_line = self.content[self.current_index]

        return

    def prev_line(self):
        global current_line

        self.prev()
        current_line = self.content[self.current_index]

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
def active_help():
    return ('active', "mark a task active")
    
def do_active(params):
    if len(params) < 1:
        print("? must provide at least one task name")
        sys.exit(1)
    for ii in params:
        t = get_task(ii)
        if not t:
            continue
        fullpath = task_name_exists(ii)
        t.set_state(ACTIVE)
        t.add_note("marked active")
        put_task(t, overwrite=False)
        t.print()
        os.remove(fullpath)
    return

def add_help():
    return ('add', "add open task: <name> <project> <priority> <description>")
    
def do_add(params):
    task = Task()
    if len(params) < 4:
        print("? %s" % add_help())
        p = ' '.join(params)
        p.replace('[','')
        p.replace(']','')
        p.replace('.','')
        print("  got: %s" % p)
        return

    if params[0] == 'next':
        tname = dbs_next()
    if task_name_exists(tname):
        print("? a task by that name (\"%s\") already exists" % tname)
        sys.exit(1)

    task.set_name(tname)
    task.set_project(params[1])
    task.set_priority(params[2])
    task.set_task(' '.join(params[3:]))
    task.set_state(OPEN)
    task.add_note("created")

    task.write()
    task.print()

    return

def delete_help():
    return ('delete', "delete one or more tasks: <name> ...")
    
def do_delete(params):
    if len(params) < 1:
        print("? must provide at least one task name")
        sys.exit(1)

    for ii in params:
        t = get_task(ii)
        if not t:
            continue
        fullpath = task_name_exists(ii)
        t.set_state(DELETED)
        t.add_note("mark deleted")
        t.move(DELETED)
        t.print()
        os.remove(fullpath)

    return

def done_help():
    return ('done', "mark one or more tasks done: <name> ...")
    
def do_done(params):
    if len(params) < 1:
        print("? must provide at least one task name")
        sys.exit(1)

    for ii in params:
        t = get_task(ii)
        if not t:
            continue
        fullpath = task_name_exists(ii)
        t.set_state(DONE)
        t.add_note("marked done")
        t.move(DONE)
        t.print()
        os.remove(fullpath)

    return

def down_help():
    return ('down', "lower the priority of a task: <name> ...")
    
def do_down(params):
    if len(params) < 1:
        print("? must provide at least one task name")
        sys.exit(1)
    
    for ii in params:
        t = get_task(ii)
        if not t:
            continue
        pri = t.get_priority()
        if pri == HIGH:
            pri = MEDIUM
        elif pri == MEDIUM:
            pri = LOW
        else:
            print("? task \"%s\" already at '%s'" % (ii, LOW))
            continue
        t.set_priority(pri)
        t.add_note("downed priority")
        put_task(t)

    return

def dup_help():
    return ('dup', "duplicate a task: <old-name> <new-name>")
    
def do_dup(params):
    if len(params) < 2:
        print("? must provide old and new task names")
        sys.exit(1)
    
    oldtask = params[0]
    if params[1] == 'next':
        newtask = dbs_next()
    else:
        newtask = params[1]

    tnew = get_task(oldtask)
    if not tnew:        # the original to be copied does not exist
        return

    tnew.set_name(newtask)
    tnew.add_note("duplicate of %s" % oldtask)
    put_task(tnew, overwrite=False)

    return

def edit_help():
    return ('edit', "edit a task: <name>")
    
def do_edit(params):
    if len(params) < 1:
        print("? must provide a task name")
        sys.exit(1)
    
    origtask = get_task(params[0])
    if not origtask:        # the original does not exist
        return
    fullpath = task_name_exists(params[0])
    tmppath = tempfile.mktemp()
    shutil.copyfile(fullpath, tmppath)

    result = editor.edit(filename=tmppath)
    newtask = Task()
    newtask.populate(tmppath, origtask.get_name())
    if newtask.get_state() == origtask.get_state():
        put_task(newtask, overwrite=True)
    else:
        newtask.write()
        os.remove(fullpath)

    os.remove(tmppath)

    return

def inactive_help():
    return ('inactive', "move task from active to open")

def do_inactive(params):
    if len(params) < 1:
        print("? must provide at least one task name")
        sys.exit(1)

    for ii in params:
        t = get_task(ii)
        if not t:
            continue
        fullpath = task_name_exists(ii)
        t.set_state(OPEN)
        t.add_note("moved from active back to open")
        put_task(t, overwrite=False)
        t.print()
        os.remove(fullpath)
    return

def log_help():
    return ('log', "log done task: <name> <project> <priority> <description>")
    
def do_log(params):
    task = Task()
    if len(params) < 4:
        print("? %s" % log_help())
        p = ' '.join(params)
        p.replace('[','')
        p.replace(']','')
        p.replace('.','')
        print("  got: %s" % p)
        return

    if params[0] == 'next':
        tname = dbs_next()
    else:
        tname = params[0]
    if task_name_exists(tname):
        print("? a task by that name (\"%s\") already exists" % tname)
        sys.exit(1)

    task.set_name(tname)
    task.set_project(params[1])
    task.set_priority(params[2])
    task.set_task(' '.join(params[3:]))
    task.set_state(DONE)
    task.add_note("added to log")

    task.print()
    task.write()

    return

def next_help():
    return ('next', "return next unused sequence number (to use as a name)")

def do_next(params):
    print("Next usable sequence number: %s" % dbs_next())
    return

def note_help():
    return ('note', "add a note to a task: <name> <note>")
    
def do_note(params):
    if len(params) < 2:
        print("? expected -- %s" % note_help())
        print("  got: %s" % ' '.join(params))
        sys.exit(1)

    fullpath = task_name_exists(params[0])
    if not fullpath:
        print("? task \"%s\" is not defined" % params[0])
        sys.exit(1)

    t = get_task(params[0])
    if not t:
        return
    t.add_note(' '.join(params[1:]))
    put_task(t, overwrite=True)
    t.print()

    return

def num_help():
    return ('num', "print project task counts")
    
def do_num(params):
    summaries = {}
    tasks = {}

    for state in ALLOWED_STATES:
        if state == DELETED:
            continue
        fullpath = os.path.join(dbs_repo(), state)
        for (dirpath, dirnames, filenames) in os.walk(fullpath):
            for ii in filenames:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               proj = t.get_project()
               pri = t.get_priority()
               state = t.get_state()
               if proj not in summaries:
                   summaries[proj] = 0
               summaries[proj] += 1
               tasks[ii] = t

    if len(tasks) < 1:
        print("No projects found.")
        return

    print("Task counts by project:")
    print("-Name---  --Total--")
    total = 0
    for ii in sorted(summaries.keys()):
        total += summaries[ii]
        print("%s%-8s%s   %5d" % (GREEN_ON, ii, COLOR_OFF, summaries[ii]))

    print_projects_found(len(summaries))
    print_tasks_found(total, False)
    return

def priority_help():
    return ('priority', "print project task summaries by priority")
    
def do_priority(params):
    summaries = {}
    tasks = {}

    for state in ALLOWED_STATES:
        if state == DELETED:
            continue
        fullpath = os.path.join(dbs_repo(), state)
        for (dirpath, dirnames, filenames) in os.walk(fullpath):
            for ii in filenames:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               proj = t.get_project()
               pri = t.get_priority()
               state = t.get_state()
               if proj not in summaries:
                   summaries[proj] = { HIGH:0, MEDIUM:0, LOW:0, \
                                       ACTIVE:0, OPEN:0, DONE:0 }
               summaries[proj][pri] += 1
               summaries[proj][state] += 1
               tasks[ii] = t

    if len(tasks) < 1:
        print("No projects and no summaries.")
        return

    print("Summary by priority:")
    print("-Name---  --H- --M- --L-  --Total--")
    for ii in sorted(summaries.keys()):
        print("%s%-8s%s  %3d  %3d  %3d   %5d" %
              (GREEN_ON, ii, COLOR_OFF,
               summaries[ii][HIGH], summaries[ii][MEDIUM], summaries[ii][LOW],
               summaries[ii][HIGH] + summaries[ii][MEDIUM] + summaries[ii][LOW]
              ))

    print("")
    if len(summaries.keys()) > 1:
        ssuffix = 's'
    if len(tasks) > 1:
        tsuffix = 's'
    print("%d project%s with %d task%s" % (len(summaries.keys()), ssuffix,
          len(tasks), tsuffix))

    return

def projects_help():
    return ('projects', "print project task summaries")
    
def do_projects(params):
    summaries = {}
    tasks = {}

    for state in ALLOWED_STATES:
        if state == DELETED:
            continue
        fullpath = os.path.join(dbs_repo(), state)
        for (dirpath, dirnames, filenames) in os.walk(fullpath):
            for ii in filenames:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               proj = t.get_project()
               pri = t.get_priority()
               state = t.get_state()
               if proj not in summaries:
                   summaries[proj] = { HIGH:0, MEDIUM:0, LOW:0, \
                                       ACTIVE:0, OPEN:0, DONE:0 }
               summaries[proj][pri] += 1
               summaries[proj][state] += 1
               tasks[ii] = t

    if len(tasks) < 1:
        print("No projects and no summaries.")
        return

    print("Summary by priority:")
    print("-Name---  --H- --M- --L-  --Total--")
    for ii in sorted(summaries.keys()):
        print("%s%-8s%s  %3d  %3d  %3d   %5d" %
              (GREEN_ON, ii, COLOR_OFF,
               summaries[ii][HIGH], summaries[ii][MEDIUM], summaries[ii][LOW],
               summaries[ii][HIGH] + summaries[ii][MEDIUM] + summaries[ii][LOW]
              ))

    print("")
    print("Summary by state:")
    print("-Name---  -Active- -Open- -Closed-  --Total--")
    for ii in sorted(summaries.keys()):
        print("%s%-8s%s    %3d     %3d     %3d      %5d" %
            (GREEN_ON, ii, COLOR_OFF,
             summaries[ii][ACTIVE], summaries[ii][OPEN], summaries[ii][DONE],
             summaries[ii][ACTIVE] + summaries[ii][OPEN] + summaries[ii][DONE]
            ))

    print("")
    if len(summaries.keys()) > 1:
        ssuffix = 's'
    if len(tasks) > 1:
        tsuffix = 's'
    print("%d project%s with %d task%s" % (len(summaries.keys()), ssuffix,
          len(tasks), tsuffix))

    return

def recap_help():
    return ('recap', "list all tasks done or touched in <n> days: <n>")
    
def do_recap(params):
    days = 1
    if len(params) >= 1:
        if params[0].isnumeric():
            days = int(params[0])
        else:
            print("? need a numeric value for number of days")
            sys.exit(1)

    if days > DAYS_LIMIT:
        print("? no, you really don't want more than %d days worth." %
              int(days))
        sys.exit(1)

    current_time = time.time()
    elapsed_time = days * 3600 * 24

    fullpath = os.path.join(dbs_repo(), DONE)
    tasks = {}
    for (dirpath, dirnames, filenames) in os.walk(fullpath):
        for ii in filenames:
           file_time = os.path.getmtime(os.path.join(fullpath, ii))

           if current_time - file_time < elapsed_time:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               tasks[ii] = t

    if len(tasks) < 1:
        print("No %s tasks found." % DONE)
    else:
        if days == 1:
           print("Done during the last day:")
        else:
           print("Done during the last %d days:" % days)
        one_line_header()
        keys = tasks.keys()
        for pri in [HIGH, MEDIUM, LOW]:
            for ii in sorted(keys):
               if tasks[ii].get_priority() == pri:
                    tasks[ii].one_line()

    fullpath = os.path.join(dbs_repo(), ACTIVE)
    tasks = {}
    for (dirpath, dirnames, filenames) in os.walk(fullpath):
        for ii in filenames:
           file_time = os.path.getmtime(os.path.join(fullpath, ii))

           if current_time - file_time < elapsed_time:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               tasks[ii] = t

    print("")
    if len(tasks) < 1:
        print("No %s tasks touched." % ACTIVE)
    else:
        if days == 1:
            print("Active tasks touched the last day:")
        else:
            print("Active tasks touched during the last %d days:" % days)
        one_line_header()
        keys = tasks.keys()
        for pri in [HIGH, MEDIUM, LOW]:
            for ii in sorted(keys):
               if tasks[ii].get_priority() == pri:
                    tasks[ii].one_line()

    fullpath = os.path.join(dbs_repo(), OPEN)
    tasks = {}
    for (dirpath, dirnames, filenames) in os.walk(fullpath):
        for ii in filenames:
           file_time = os.path.getmtime(os.path.join(fullpath, ii))

           if current_time - file_time < elapsed_time:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               tasks[ii] = t

    print("")
    if len(tasks) < 1:
        print("No %s tasks touched." % OPEN)
    else:
        if days == 1:
            print("Open tasks touched the last day:")
        else:
            print("Open tasks touched during the last %d days:" % days)
        one_line_header()
        keys = tasks.keys()
        for pri in [HIGH, MEDIUM, LOW]:
            for ii in sorted(keys):
               if tasks[ii].get_priority() == pri:
                    tasks[ii].one_line()
    return

def state_help():
    return ('state', "print project task summaries by state")
    
def do_state():
    projects = []
    tasks = 0

    for state in ALLOWED_STATES:
        if state == DELETED or state == DONE:
            continue
        fullpath = os.path.join(dbs_repo(), state)
        for (dirpath, dirnames, filenames) in os.walk(fullpath):
            for ii in filenames:
               t = Task()
               t.populate(os.path.join(fullpath, ii), ii)
               proj = t.get_project()
               if proj not in projects:
                   projects.append(proj)
               tasks += 1

    return (len(projects), tasks)

def up_help():
    return ('up', "raise the priority of a task: <name> ...")
    
def do_up(params):
    if len(params) < 1:
        print("? must provide at least one task name")
        sys.exit(1)
    
    for ii in params:
        t = get_task(ii)
        if not t:
            continue
        pri = t.get_priority()
        if pri == LOW:
            pri = MEDIUM
        elif pri == MEDIUM:
            pri = HIGH
        else:
            print("? task \"%s\" already at '%s'" % (ii, HIGH))
            continue
        t.set_priority(pri)
        t.add_note("upped priority")
        put_task(t)

    return

#-- main
def help_j():
    return ('j', "Next task")

def help_k():
    return ('k', "Previous task")

def help_N():
    return ('ctrl-N', "Next project")

def help_P():
    return ('ctrl-P', "Previous project")

def help_R():
    return ('ctrl-R', "Refresh all project and task info")

def help_KEY_DOWN():
    return ('<down arrow>', "Next task")

def help_KEY_UP():
    return ('<up arrow>', "Previous task")

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
    win.addstr(0, 0, options, BOLD_WHITE_ON_BLUE)
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

def refresh_cli(screen, win, msg):
    maxy, maxx = win.getmaxyx()
    if len(msg) > 0:
        win.addstr(0, 0, msg, BOLD_RED_ON_BLACK)
    return

def refresh_projects(screen, win, lines):
    global current_project
    global DBG

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
        win.addch(linenum, PROJECT_WIDTH-1, "|", BLUE_ON_BLACK)
        # DBG.write('refresh_projects: ' + str(linenum))
        linenum += 1
        if linenum >= maxy - 1:
            return

    while linenum < maxy-1:
        win.addch(linenum, PROJECT_WIDTH-1, "|", BLUE_ON_BLACK)
        linenum += 1

    return


def get_current_task_list(current_project):
    global ACTIVE_PROJECTS, ALL_TASKS, ACTIVE_TASKS
    global current_task
    global DBG

    DBG.write('get_current_task_list: ' + current_project)
    ACTIVE_TASKS.clear()
    task_list = []
    task_list = ACTIVE_PROJECTS[current_project][HIGH] + \
                ACTIVE_PROJECTS[current_project][MEDIUM] + \
                ACTIVE_PROJECTS[current_project][LOW]
    for ii in task_list:
        t = ALL_TASKS[ii.get_name()]
        if t.get_name() not in ACTIVE_TASKS:
            ACTIVE_TASKS[t.get_name()] = ii

    tlist = sorted(ACTIVE_TASKS.keys())
    current_task = tlist[0]

    return tlist

def refresh_tasks(screen, win, lines):
    global ACTIVE_TASKS, current_task

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
        if ACTIVE_TASKS[tname].get_state() == ACTIVE:
            attrs = BOLD_WHITE_ON_BLUE
        if tname == current_task:
            attrs = BOLD_WHITE_ON_RED
        txt = "%5.5s  %4s  %1s  %s" % (info[0], info[1], info[2], info[3])
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
        win.addstr(linenum, 0, ii, attrs)
        # DBG.write('refresh_list: <' + str(linenum) + '> ' + ii)
        linenum += 1
        if linenum >= maxy - 1:
            return

    return

def help_help():
    return ('?', "help (show this list)")
    
def help_p00():
    return ('p00', 'just some command text p00')
def help_p01():
    return ('p01', 'just some command text p01')
def help_p02():
    return ('p02', 'just some command text p02')
def help_p03():
    return ('p03', 'just some command text p03')
def help_p04():
    return ('p04', 'just some command text p04')
def help_p05():
    return ('p05', 'just some command text p05')
def help_p06():
    return ('p06', 'just some command text p06')
def help_p07():
    return ('p07', 'just some command text p07')
def help_p08():
    return ('p08', 'just some command text p08')
def help_p09():
    return ('p09', 'just some command text p09')
    
def help_cb(win, maxx, linenum, line):
    info = line.split('\t')
    win.addstr(linenum, 0, info[0], BOLD_PLAIN_TEXT)
    win.addstr(linenum, 15, info[1], PLAIN_TEXT)
    return

def refresh_help():
    CMDLIST = []
    for ii in globals().keys():
        if HELP_PREFIX.search(str(ii)):
            if str(ii) == 'help_cb':
                continue
            CMDLIST.append(str(ii))
    cmds = sorted(CMDLIST)

    clines = []
    for ii in sorted(cmds):
        (key, info) = globals()[ii]()
        info = '%-14s   %s' % (key, info)
        clines.append(info)

    return clines

def help_o():
    return ('o', "Open and display the current task")

def open_cb(win, maxx, linenum, line):
    info = line.split(':')
    if len(info) < 2:
        return
    win.addstr(linenum, 0, '%s:' % info[0], BOLD_PLAIN_TEXT)
    win.addstr(linenum, len(info[0])+1, '%s' % (' '.join(info[1:])), PLAIN_TEXT)
    return

def refresh_open(windows, page):
    global ACTIVE_TASKS, current_task

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]
    tinfo = ACTIVE_TASKS[current_task].show_text()
    tlines = tinfo.split('\n')

    page = show_page(win, trailer, 'Open Task', page, tlines, open_cb)
    return page

def help_D():
    return ('D', "List all done tasks")

def refresh_done(windows, page):
    global ALL_TASKS, current_project

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]
    task_list = collections.OrderedDict()
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_state() == DONE:
            if t.get_name() not in task_list:
                task_list[t.get_name()] = t

    tlines = []
    for ii in sorted(task_list):
        t = task_list[ii]
        info = '%4.4s\t' % t.get_name()
        info += '%7.7s\t' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]\t' % t.note_count()
        else:
            info += '     \t'
        info += '%1s\t' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    page = show_page(win, trailer, 'List of Tasks Done', page, tlines, all_cb)
    return page

def help_A():
    return ('A', "List all active tasks")

def refresh_task_list():
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
        info = '%4.4s  ' % t.get_name()
        info += '%7.7s  ' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]  ' % t.note_count()
        else:
            info += '       '
        info += '%1s  ' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    return sorted(tlines)

def help_ctrl_A():
    return ('ctrl-A', "List ALL tasks, in any state")

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

def refresh_all(windows, page):
    global ALL_TASKS, current_project

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]

    tlines = []
    for ii in sorted(ALL_TASKS):
        t = ALL_TASKS[ii]
        info = '%4.4s\t' % t.get_name()
        if t.get_state() == DELETED:
            info += '%1.1s\t' % 'D'
        else:
            info += '%1.1s\t' % t.get_state()[0:1]
        info += '%7.7s\t' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]\t' % t.note_count()
        else:
            info += '     \t'
        info += '%1s\t' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    page = show_page(win, trailer, 'List of All Tasks', page, tlines,
                     all_with_state_cb)
    return page

def help_ctrl_D():
    return ('ctrl-D', "List all deleted tasks")

def refresh_deleted(windows, page):
    global ALL_TASKS, current_project

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]
    task_list = collections.OrderedDict()
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_state() == DELETED:
            if t.get_name() not in task_list:
                task_list[t.get_name()] = t

    tlines = []
    for ii in sorted(task_list):
        t = task_list[ii]
        info = '%4.4s\t' % t.get_name()
        info += '%7.7s\t' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]\t' % t.note_count()
        else:
            info += '     \t'
        info += '%1s\t' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    page = show_page(win, trailer, 'List of Deleted Tasks', page, tlines,
                     all_cb)
    return page

def help_ctrl_O():
    return ('ctrl-O', "List all open tasks")

def refresh_all_open(windows, page):
    global ALL_TASKS, current_project

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]
    task_list = collections.OrderedDict()
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_state() == OPEN:
            if t.get_name() not in task_list:
                task_list[t.get_name()] = t

    tlines = []
    for ii in sorted(task_list):
        t = task_list[ii]
        info = '%4.4s\t' % t.get_name()
        info += '%7.7s\t' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]\t' % t.note_count()
        else:
            info += '     \t'
        info += '%1s\t' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    page = show_page(win, trailer, 'List of Open Tasks', page, tlines,
                     all_cb)
    return page

def help_S():
    return ('S', "List project state counts")

def refresh_states(windows, page):
    global ALL_TASKS, current_project

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]
    task_list = collections.OrderedDict()
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_state() == OPEN:
            if t.get_name() not in task_list:
                task_list[t.get_name()] = t

    tlines = []
    for ii in sorted(task_list):
        t = task_list[ii]
        info = '%4.4s\t' % t.get_name()
        info += '%7.7s\t' % t.get_project()
        if t.note_count() > 0:
            info += '[%.2d]\t' % t.note_count()
        else:
            info += '     \t'
        info += '%1s\t' % t.get_priority()
        info += '%s' % t.get_task()
        tlines.append(info)

    page = show_page(win, trailer, 'List of Open Tasks', page, tlines,
                     all_cb)
    return page

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
    global current_project

    windows = {}
    curses.curs_set(0)
    stdscr.clear()
    maxy, maxx = stdscr.getmaxyx()

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
    prev_mode = MAIN_MODE
    mode = MAIN_MODE
    while True:
        stdscr.clear()
        maxy, maxx = stdscr.getmaxyx()

        DBG.write('state: %d; mode: %s' % (state, mode))
        windows[HEADER_PANEL].refresh(mode)
        windows[TRAILER_PANEL].refresh(mode)
        windows[CLI_PANEL].refresh(mode)
        windows[PROJ_PANEL].refresh(mode)
        windows[TASK_PANEL].refresh(mode)

        if mode == ERROR_MODE:
            windows[HEADER_PANEL].set_mode(ERROR_MODE, text=MAIN_OPTIONS)
            mode = prev_mode

        if state != 0:
            windows[LIST_PANEL].refresh(mode)

        curses.panel.update_panels()
        stdscr.refresh()
        key = stdscr.getkey()
        DBG.write('main: getkey "%s"' % key)

        if state == 0:
            if key == 'q' or key == curses.KEY_EXIT:
                break

            elif key == 'v':
                mode = VERSION_MODE
                state = 0

            elif key == '?':
                prev_mode = mode
                mode = HELP_MODE
                windows[PROJ_PANEL].hide()
                windows[TASK_PANEL].hide()
                windows[LIST_PANEL].set_mode(HELP_MODE)
                windows[LIST_PANEL].set_content(refresh_help())
                windows[LIST_PANEL].refresh(HELP_MODE)
                windows[LIST_PANEL].show()
                state = 10

            elif key == 'j' or key == curses.KEY_DOWN:
                windows[TASK_PANEL].next_task()

            elif key == 'k' or key == curses.KEY_UP:
                windows[TASK_PANEL].prev_task()

#           elif key == '':
#               mode = 'list_page'
#               options = 'All || -: PrevPage   <space>: NextPage   q: Quit'
#               page[LIST_PANEL] = refresh_all(windows, 0)
#               panels[PROJ_PANEL].hide()
#               panels[TASK_PANEL].hide()
#               panels[LIST_PANEL].show()
#               state = 50

#           elif key == '':
#               mode = 'list_page'
#               options = 'Deleted || -: PrevPage   <space>: NextPage   q: Quit'
#               page[LIST_PANEL] = refresh_deleted(windows, 0)
#               panels[PROJ_PANEL].hide()
#               panels[TASK_PANEL].hide()
#               panels[LIST_PANEL].show()
#               state = 60

            elif key == '':
                windows[PROJ_PANEL].next_project()
                windows[TASK_PANEL].populate()

#           elif key == '':
#               mode = 'list_page'
#               options = 'All Open || -: PrevPage   <space>: NextPage   q: Quit'
#               page[LIST_PANEL] = refresh_all_open(windows, 0)
#               panels[PROJ_PANEL].hide()
#               panels[TASK_PANEL].hide()
#               panels[LIST_PANEL].show()
#               state = 60

            elif key == '':
                windows[PROJ_PANEL].prev_project()
                windows[TASK_PANEL].populate()

#           elif key == '':
#               current_project = ''
#               current_task = ''
#               build_task_info()

#           elif key == 'o':
#               mode = 'open'
#               options = 'Open || -: PrevPage   <space>: NextPage   q: Quit'
#               page[LIST_PANEL] = refresh_open(windows, 0)
#               panels[PROJ_PANEL].hide()
#               panels[TASK_PANEL].hide()
#               panels[LIST_PANEL].show()
#               state = 20

            elif key == 'A':
                prev_mode = mode
                mode = TASK_LIST_MODE
                windows[PROJ_PANEL].hide()
                windows[TASK_PANEL].hide()
                windows[LIST_PANEL].set_mode(TASK_LIST_MODE,
                                             text=TASK_LIST_OPTIONS)
                windows[LIST_PANEL].set_content(refresh_task_list())
                windows[LIST_PANEL].refresh(TASK_LIST_MODE)
                windows[LIST_PANEL].show()
                state = 10

#           elif key == 'D':
#               mode = 'list_page'
#               options = 'Done || -: PrevPage   <space>: NextPage   q: Quit'
#               page[LIST_PANEL] = refresh_done(windows, 0)
#               panels[PROJ_PANEL].hide()
#               panels[TASK_PANEL].hide()
#               panels[LIST_PANEL].show()
#               state = 30

            elif key == 'KEY_RESIZE' or key == curses.KEY_RESIZE:
                if curses.is_term_resized(maxy, maxx):
                    resize_windows(stdscr, windows)
                state = 0

            elif key == '\n':
                state = 0

#           elif key == 'S':
#               mode = 'list_page'
#               options = 'States || -: PrevPage   <space>: NextPage   q: Quit'
#               page[LIST_PANEL] = refresh_states(windows, 0)
#               panels[PROJ_PANEL].hide()
#               panels[TASK_PANEL].hide()
#               panels[LIST_PANEL].show()
#               state = 80

            else:
                prev_mode = mode
                mode = ERROR_MODE
                msg = "? no such command: %s" % str(key)
                windows[CLI_PANEL].set_mode(ERROR_MODE, text=msg)
                state = 0
                
        elif state == 10:
            if key == 'q':
                prev_mode = mode
                mode = MAIN_MODE
                windows[LIST_PANEL].set_mode(MAIN_MODE)
                windows[LIST_PANEL].hide()
                windows[PROJ_PANEL].show()
                windows[TASK_PANEL].show()
                state = 0
            elif key == 'j':
                windows[LIST_PANEL].next_line()
            elif key == 'k':
                windows[LIST_PANEL].prev_line()
            elif key == 'KEY_RESIZE' or key == curses.KEY_RESIZE:
                if curses.is_term_resized(maxy, maxx):
                    resize_windows(stdscr, windows)
            else:
                prev_mode = mode
                mode = ERROR_MODE
                windows[HEADER_PANEL].set_mode(ERROR_MODE, text=HELP_OPTIONS)
                msg = "? no such command: %s" % str(key)
                windows[CLI_PANEL].set_mode(ERROR_MODE, text=msg)
                state = 10

#       elif state == 20:
#           if key == 'q':
#               mode = 'main'
#               options = MAIN_OPTIONS
#               panels[LIST_PANEL].hide()
#               panels[PROJ_PANEL].show()
#               panels[TASK_PANEL].show()
#               page[PROJ_PANEL] = 0
#               page[TASK_PANEL] = 0
#               state = 0
#           elif key == '-':
#               page[LIST_PANEL] = refresh_open(windows, page[LIST_PANEL]-1)
#           elif key == ' ':
#               page[LIST_PANEL] = refresh_open(windows, page[LIST_PANEL]+1)
#           else:
#               page[LIST_PANEL] = refresh_open(windows, page[LIST_PANEL])
#               state = 20

#       elif state == 30:
#           if key == 'q':
#               mode = 'main'
#               options = MAIN_OPTIONS
#               panels[LIST_PANEL].hide()
#               panels[PROJ_PANEL].show()
#               panels[TASK_PANEL].show()
#               page[PROJ_PANEL] = 0
#               page[TASK_PANEL] = 0
#               page = 0
#               state = 0
#           elif key == '-':
#               page[LIST_PANEL] = refresh_done(windows, page[LIST_PANEL]-1)
#           elif key == ' ':
#               page[LIST_PANEL] = refresh_done(windows, page[LIST_PANEL]+1)
#           else:
#               page[LIST_PANEL] = refresh_done(windows, page[LIST_PANEL])
#               state = 30

#       elif state == 40:
#           if key == 'q':
#               mode = 'main'
#               options = MAIN_OPTIONS
#               panels[LIST_PANEL].hide()
#               panels[PROJ_PANEL].show()
#               panels[TASK_PANEL].show()
#               page[PROJ_PANEL] = 0
#               page[TASK_PANEL] = 0
#               page = 0
#               state = 0
#           elif key == '-':
#               page[LIST_PANEL] = refresh_active(windows, page[LIST_PANEL]-1)
#           elif key == ' ':
#               page[LIST_PANEL] = refresh_active(windows, page[LIST_PANEL]+1)
#           else:
#               page[LIST_PANEL] = refresh_active(windows, page[LIST_PANEL])
#               state = 40

#       elif state == 50:
#           if key == 'q':
#               mode = 'main'
#               options = MAIN_OPTIONS
#               panels[LIST_PANEL].hide()
#               panels[PROJ_PANEL].show()
#               panels[TASK_PANEL].show()
#               page[PROJ_PANEL] = 0
#               page[TASK_PANEL] = 0
#               page = 0
#               state = 0
#           elif key == '-':
#               page[LIST_PANEL] = refresh_all(windows, page[LIST_PANEL]-1)
#           elif key == ' ':
#               page[LIST_PANEL] = refresh_all(windows, page[LIST_PANEL]+1)
#           else:
#               page[LIST_PANEL] = refresh_all(windows, page[LIST_PANEL])
#               state = 50

#       elif state == 60:
#           if key == 'q':
#               mode = 'main'
#               options = MAIN_OPTIONS
#               panels[LIST_PANEL].hide()
#               panels[PROJ_PANEL].show()
#               panels[TASK_PANEL].show()
#               page[PROJ_PANEL] = 0
#               page[TASK_PANEL] = 0
#               page = 0
#               state = 0
#           elif key == '-':
#               page[LIST_PANEL] = refresh_deleted(windows, page[LIST_PANEL]-1)
#           elif key == ' ':
#               page[LIST_PANEL] = refresh_deleted(windows, page[LIST_PANEL]+1)
#           else:
#               page[LIST_PANEL] = refresh_deleted(windows, page[LIST_PANEL])
#               state = 60

#       elif state == 70:
#           if key == 'q':
#               mode = 'main'
#               options = MAIN_OPTIONS
#               panels[LIST_PANEL].hide()
#               panels[PROJ_PANEL].show()
#               panels[TASK_PANEL].show()
#               page[PROJ_PANEL] = 0
#               page[TASK_PANEL] = 0
#               page = 0
#               state = 0
#           elif key == '-':
#               page[LIST_PANEL] = refresh_all_open(windows, page[LIST_PANEL]-1)
#           elif key == ' ':
#               page[LIST_PANEL] = refresh_all_open(windows, page[LIST_PANEL]+1)
#           else:
#               page[LIST_PANEL] = refresh_all_open(windows, page[LIST_PANEL])
#               state = 70

#       elif state == 80:
#           if key == 'q':
#               mode = 'main'
#               options = MAIN_OPTIONS
#               panels[LIST_PANEL].hide()
#               panels[PROJ_PANEL].show()
#               panels[TASK_PANEL].show()
#               page[PROJ_PANEL] = 0
#               page[TASK_PANEL] = 0
#               page = 0
#               state = 0
#           elif key == '-':
#               page[LIST_PANEL] = refresh_states(windows, page[LIST_PANEL]-1)
#           elif key == ' ':
#               page[LIST_PANEL] = refresh_states(windows, page[LIST_PANEL]+1)
#           else:
#               page[LIST_PANEL] = refresh_states(windows, page[LIST_PANEL])
#               state = 80

    return

#-- link to main
def dbsui_main():
    global DBG

    DBG = Debug()
    curses.wrapper(dbsui)
    DBG.done()

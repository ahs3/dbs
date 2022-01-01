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
ALL_PROJECTS = collections.OrderedDict()
ALL_TASKS = collections.OrderedDict()

current_project = ''
current_task = ''

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

MAIN_OPTIONS = 'DBS || q: Quit   o: Open   ?: Help'

DBG = None
PROJECT_WIDTH = 20

#-- classes
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

def show_error(win, msg, attrs):
    maxy, maxx = win.getmaxyx()
    blanks = ' '.ljust(maxx-1, ' ')
    win.addstr(0, 0, blanks, attrs)
    win.addstr(0, 0, msg, attrs)
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
    win.erase()
    win.addstr(0, 0, blanks, BOLD_WHITE_ON_BLUE)
    win.addstr(0, 0, options, BOLD_WHITE_ON_BLUE)
    return

def refresh_trailer(win, msg):
    (height, width) = win.getmaxyx()
    dashes = ''.ljust(width-1, '-')
    win.erase()
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

def clear_cli(win):
    maxy, maxx = win.getmaxyx()
    blanks = ' '.ljust(maxx-1, ' ')
    win.addstr(0, 0, blanks, PLAIN_TEXT)
    return

def refresh_project_list(screen, win, adjustment):
    global ACTIVE_PROJECTS, current_project

    win.erase()
    win.mvwin(1, 0)
    (sheight, swidth) = screen.getmaxyx()
    (height, width) = win.getmaxyx()
    blanks = ''.ljust(PROJECT_WIDTH-1, ' ')

    for ii in range(0, height-1):
        win.addch(ii, PROJECT_WIDTH-1, "|", BLUE_ON_BLACK)

    line = 0
    count = 0
    keys = ACTIVE_PROJECTS.keys()
    for ii in sorted(keys):
        p = ACTIVE_PROJECTS[ii]
        if count < adjustment:
            count += 1
            continue

        if line >= height - 1:
            return count

        if not current_project:
            current_project = ii

        active = p[ACTIVE]
        if ii == current_project:
            attrs = BOLD_WHITE_ON_RED
        else:
            if active > 0:
                attrs = BOLD_GREEN_ON_BLACK
            else:
                attrs = PLAIN_TEXT
        win.addstr(line, 0, blanks, attrs)
        pname = ii[0:PROJECT_WIDTH-1]
        if active > 0:
            win.addstr(line, 0, "%s [%d]" % (pname, active), attrs)
        else:
            win.addstr(line, 0, "%s" % (pname), attrs)
        line += 1
        count += 1

    return 0

def current_project_next():
    global ACTIVE_PROJECTS, current_project

    keys = ACTIVE_PROJECTS.keys()
    now = False
    for ii in sorted(keys):
        if now:
            current_project = ii
            return
        if current_project == ii:
            now = True

    return

def current_project_prev():
    global ACTIVE_PROJECTS, current_project

    keys = ACTIVE_PROJECTS.keys()
    last = ''
    for ii in sorted(keys):
        if current_project == ii:
            current_project = last
            return
        last = ii

    return

def refresh_task_list(screen, win, adjustment):
    global ACTIVE_PROJECTS, ALL_TASKS, current_project, current_task

    (sheight, swidth) = screen.getmaxyx()
    win.erase()
    (height, width) = win.getmaxyx()
    blanks = ''.ljust(swidth - PROJECT_WIDTH -1, ' ')

    line = 0
    count = 0

    task_list = []
    task_list = ACTIVE_PROJECTS[current_project][HIGH] + \
                ACTIVE_PROJECTS[current_project][MEDIUM] + \
                ACTIVE_PROJECTS[current_project][LOW]

    if current_task not in task_list:
        current_task = ''

    for ii in task_list:
        t = ALL_TASKS[ii.get_name()]

        if count < adjustment:
            count += 1
            continue

        if line >= height - 1:
            return count

        active = False
        s = t.get_state()

        if not current_task:
            current_task = ii

        if s == ACTIVE:
            active = True

        if ii == current_task:
            attrs = BOLD_WHITE_ON_RED
        else:
            if active:
                attrs = BOLD_GREEN_ON_BLACK
            else:
                pri = t.get_priority()
                if pri == HIGH:
                    attrs = RED_ON_BLACK
                elif pri == MEDIUM:
                    attrs = GREEN_ON_BLACK
                else:
                    attrs = PLAIN_TEXT

        win.addstr(line, 0, blanks, attrs)
        info = '%4.4s' % t.get_name()
        if t.note_count() > 0:
            info += ' [%2d]' % t.note_count()
        else:
            info += '     '
        info += ' %1s' % t.get_priority()
        info += ' %s' % t.get_task()
        length = (width - 1)
        win.addstr(line, 0, "%s" % (info[0:length]), attrs)
        line += 1
        count += 1

    return 0

def current_task_next():
    global ACTIVE_PROJECTS, current_task

    task_list = []
    task_list = ACTIVE_PROJECTS[current_project][HIGH] + \
                ACTIVE_PROJECTS[current_project][MEDIUM] + \
                ACTIVE_PROJECTS[current_project][LOW]

    now = False
    for ii in task_list:
        if now:
            current_task = ii
            return
        if current_task == ii:
            now = True

    return

def current_task_prev():
    global ACTIVE_PROJECTS, current_task

    task_list = []
    task_list = ACTIVE_PROJECTS[current_project][HIGH] + \
                ACTIVE_PROJECTS[current_project][MEDIUM] + \
                ACTIVE_PROJECTS[current_project][LOW]

    last = ''
    for ii in task_list:
        if current_task == ii:
            current_task = last
            return
        last = ii

    return

def show_page(win, trailer, trailer_text, page, lines, line_callback):
    (maxy, maxx) = win.getmaxyx()
    blanks = ''.ljust(maxx-1, ' ')
    win.erase()

    pages = int(len(lines) / maxy)
    if len(lines) % maxy > 0 and len(lines) > maxy:
        pages += 1
    if page >= pages:
        page = pages - 1
    if page < 0:
        page = 0
    start = page * maxy
    DBG.write('pages %d, start %d' % (pages, start))

    count = 0
    while count < maxy and start < len(lines):
        line_callback(win, maxx, count, lines[start])
        count += 1
        start += 1

    percent = (start / len(lines)) * 100.0
    #DBG.write(
    #  'show_page: page %d, pages %d, start %d, len(lines) %d, percent %d' %
    #  (page, pages, start, len(lines), percent))
    refresh_trailer(trailer, ' %s (%d%%) ' % (trailer_text, percent))
    return page

def help_help():
    return ('?', "help (show this list)")
    
def help_cb(win, maxx, linenum, line):
    info = line.split('\t')
    win.addstr(linenum, 0, info[0], BOLD_PLAIN_TEXT)
    win.addstr(linenum, 15, info[1], PLAIN_TEXT)
    return

def refresh_help(windows, page):
    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]

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
        info = '%s\t%s' % (key, info)
        clines.append(info)

    page = show_page(win, trailer, 'Command List', page, sorted(clines),
                     help_cb)
    return page

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
    global ALL_TASKS, current_task

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]
    tinfo = current_task.show_text()
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

def refresh_active(windows, page):
    global ALL_TASKS, current_project

    win = windows[LIST_PANEL]
    trailer = windows[TRAILER_PANEL]
    task_list = collections.OrderedDict()
    for ii in ALL_TASKS:
        t = ALL_TASKS[ii]
        if t.get_state() == ACTIVE:
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

    page = show_page(win, trailer, 'List of Active Tasks', page, tlines, 
                     all_cb)
    return page

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
    windows = {}
    panels = {}

    screen.clear()

    # how big is the screen?
    maxy, maxx = screen.getmaxyx()
    DBG.write('build: maxy, maxx: %d, %d' % (maxy, maxx))

    # create header: blue bkgrd, white text, top line
    key = HEADER_PANEL
    windows[key] = screen.subwin(1, maxx, 0, 0)
    panels[key] = curses.panel.new_panel(windows[key])
    DBG.write('hdr: h,w,y,x: %d, %d, %d, %d' % (1, maxx, 0, 0))

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

    # create trailer: same, but summary of #projects, #tasks
    key = TRAILER_PANEL
    windows[key] = screen.subwin(1, maxx, maxy-2, 0)
    panels[key] = curses.panel.new_panel(windows[key])
    DBG.write('trlr: h,w,y,x: %d, %d, %d, %d' % (1, maxx, maxy-2, 0))

    # create command: black bkgrd, white text, bottom line of screen
    key = CLI_PANEL
    windows[key] = screen.subwin(1, maxx, maxy-1, 0)
    panels[key] = curses.panel.new_panel(windows[key])
    DBG.write('cli: h,w,y,x: %d, %d, %d, %d' % (1, maxx, maxy-1, 0))

    # create several screens and panels, then hide them for later use
    # (help, show and done, for now)
    main_height = maxy - 3
    for ii in [LIST_PANEL]:
        windows[ii] = screen.subwin(main_height, maxx, 1, 0)
        panels[ii] = curses.panel.new_panel(windows[ii])
        DBG.write('%s: h,w,y,x: %d, %d, %d, %d' % (ii, main_height, maxx, 1, 0))

    DBG.write('end build')
    return (windows, panels)

def resize_windows(screen, windows):
    # how big is the screen?
    maxy, maxx = screen.getmaxyx()
    screen.resize(maxy, maxx)
    screen.erase()

    DBG.write('resize: y,x: %d, %d' % (maxy, maxx))

    windows[HEADER_PANEL].resize(1, maxx)
    windows[HEADER_PANEL].mvwin(0, 0)
    DBG.write('hdr: h,w,y,x: %d, %d, %d, %d' % (1, maxx, 0, 0))

    # project list: 1/4, left of screen
    main_height = maxy - 3
    prj_width = PROJECT_WIDTH
    windows[PROJ_PANEL].resize(main_height, prj_width)
    windows[PROJ_PANEL].mvwin(1, 0)
    DBG.write('prj: h,w,y,x: %d, %d, %d, %d' % (main_height, prj_width, 1, 0))

    # task list: 3/4, right of screen
    tsk_width = maxx - prj_width
    windows[TASK_PANEL].resize(main_height, tsk_width-1)
    windows[TASK_PANEL].mvwin(1, prj_width)
    DBG.write('tsk: h,w,y,x: %d, %d, %d, %d' % (main_height, tsk_width-1, 1, prj_width))

    windows[TRAILER_PANEL].resize(1, maxx)
    windows[TRAILER_PANEL].mvwin(maxy-2, 0)
    DBG.write('trlr: h,w,y,x: %d, %d, %d, %d' % (1, maxx, maxy-2, 0))

    windows[CLI_PANEL].resize(1, maxx)
    windows[CLI_PANEL].mvwin(maxy-1, 0)
    DBG.write('cli: h,w,y,x: %d, %d, %d, %d' % (1, maxx, maxy-1, 0))

    # update several screens and panels
    # (help, show and done, for now)
    main_height = maxy - 3
    for ii in [LIST_PANEL]:
        windows[ii].resize(main_height, maxx)
        windows[ii].mvwin(1, 0)
        DBG.write('%s: h,w,y,x: %d, %d, %d, %d' % (ii, main_height, maxx, 1, 0))

    for ii in windows:
        windows[ii].erase()

    DBG.write('end resize')
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
    windows, panels = build_windows(stdscr)

    # set up our initial state
    projects_adjustment = 0
    tasks_adjustment = 0

    page = 0
    state = 0
    options = MAIN_OPTIONS
    mode = 'main'
    while True:
        refresh_header(stdscr, windows[HEADER_PANEL], options)

        if mode not in ['version', 'error']:
            clear_cli(windows[CLI_PANEL])
        elif mode in ['list_page' ]:
            pass
        else:
            mode = 'main'

        if mode == 'main':
            refresh_trailer(windows[TRAILER_PANEL], '')
            projects_adjustment = refresh_project_list(stdscr, 
                                   windows[PROJ_PANEL],
                                           projects_adjustment)
            tasks_adjustment = refresh_task_list(stdscr, windows[TASK_PANEL],
                           tasks_adjustment)

        curses.panel.update_panels()
        stdscr.refresh()
        key = stdscr.getkey()
        DBG.write('main: getkey "%s"' % key)

        if state == 0:
            if key == 'q' or key == curses.KEY_EXIT:
                break

            elif key == 'v':
                mode = 'version'
                show_version(windows[CLI_PANEL], PLAIN_TEXT)
                state = 0

            elif key == '?':
                options = 'Help || -: PrevPage   <space>: NextPage   q: Quit'
                mode = 'list_page'
                panels[PROJ_PANEL].hide()
                panels[TASK_PANEL].hide()
                page = refresh_help(windows, 0)
                panels[LIST_PANEL].show()
                state = 10

            elif key == 'j' or key == curses.KEY_DOWN:
                current_task_next()
                tasks_adjustment = refresh_task_list(stdscr, 
                                                     windows[TASK_PANEL],
                                                     tasks_adjustment)

            elif key == 'k' or key == curses.KEY_UP:
                current_task_prev()
                tasks_adjustment = refresh_task_list(stdscr, 
                                                     windows[TASK_PANEL],
                                                     tasks_adjustment)

            elif key == '':
                mode = 'list_page'
                options = 'All || -: PrevPage   <space>: NextPage   q: Quit'
                page = refresh_all(windows, 0)
                panels[PROJ_PANEL].hide()
                panels[TASK_PANEL].hide()
                panels[LIST_PANEL].show()
                state = 50

            elif key == '':
                mode = 'list_page'
                options = 'Deleted || -: PrevPage   <space>: NextPage   q: Quit'
                page = refresh_deleted(windows, 0)
                panels[PROJ_PANEL].hide()
                panels[TASK_PANEL].hide()
                panels[LIST_PANEL].show()
                state = 60

            elif key == '':
                current_project_next()
                projects_adjustment = refresh_project_list(stdscr,
                                                           windows[PROJ_PANEL],
                                                           projects_adjustment)

            elif key == '':
                mode = 'list_page'
                options = 'All Open || -: PrevPage   <space>: NextPage   q: Quit'
                page = refresh_all_open(windows, 0)
                panels[PROJ_PANEL].hide()
                panels[TASK_PANEL].hide()
                panels[LIST_PANEL].show()
                state = 60

            elif key == '':
                current_project_prev()
                projects_adjustment = refresh_project_list(stdscr,
                                                           windows[PROJ_PANEL],
                                                           projects_adjustment)

            elif key == '':
                current_project = ''
                current_task = ''
                build_task_info()

            elif key == 'o':
                mode = 'open'
                options = 'Open || -: PrevPage   <space>: NextPage   q: Quit'
                page = refresh_open(windows, 0)
                panels[PROJ_PANEL].hide()
                panels[TASK_PANEL].hide()
                panels[LIST_PANEL].show()
                state = 20

            elif key == 'D':
                mode = 'list_page'
                options = 'Done || -: PrevPage   <space>: NextPage   q: Quit'
                page = refresh_done(windows, 0)
                panels[PROJ_PANEL].hide()
                panels[TASK_PANEL].hide()
                panels[LIST_PANEL].show()
                state = 30

            elif key == 'KEY_RESIZE' or key == curses.KEY_RESIZE:
                if curses.is_term_resized(maxy, maxx):
                    resize_windows(stdscr, windows)
                state = 0

            elif key == 'A':
                mode = 'list_page'
                options = 'Active || -: PrevPage   <space>: NextPage   q: Quit'
                page = refresh_active(windows, 0)
                panels[PROJ_PANEL].hide()
                panels[TASK_PANEL].hide()
                panels[LIST_PANEL].show()
                state = 40

            elif key == 'S':
                mode = 'list_page'
                options = 'States || -: PrevPage   <space>: NextPage   q: Quit'
                page = refresh_states(windows, 0)
                panels[PROJ_PANEL].hide()
                panels[TASK_PANEL].hide()
                panels[LIST_PANEL].show()
                state = 80

            else:
                mode = 'error'
                msg = "? no such command: %s" % str(key)
                show_error(windows[CLI_PANEL], msg, BOLD_RED_ON_BLACK)
                state = 0
                
        elif state == 10:
            if key == 'q':
                mode = 'main'
                options = MAIN_OPTIONS
                panels[LIST_PANEL].hide()
                panels[PROJ_PANEL].show()
                panels[TASK_PANEL].show()
                page = 0
                state = 0
            elif key == '-':
                page = refresh_help(windows, page-1)
            elif key == ' ':
                page = refresh_help(windows, page+1)
            else:
                page = refresh_help(windows, page)
                state = 10

        elif state == 20:
            if key == 'q':
                mode = 'main'
                options = MAIN_OPTIONS
                panels[LIST_PANEL].hide()
                panels[PROJ_PANEL].show()
                panels[TASK_PANEL].show()
                page = 0
                state = 0
            elif key == '-':
                page = refresh_open(windows, page-1)
            elif key == ' ':
                page = refresh_open(windows, page+1)
            else:
                page = refresh_open(windows, page)
                state = 20

        elif state == 30:
            if key == 'q':
                mode = 'main'
                options = MAIN_OPTIONS
                panels[LIST_PANEL].hide()
                panels[PROJ_PANEL].show()
                panels[TASK_PANEL].show()
                page = 0
                state = 0
            elif key == '-':
                page = refresh_done(windows, page-1)
            elif key == ' ':
                page = refresh_done(windows, page+1)
            else:
                page = refresh_done(windows, page)
                state = 30

        elif state == 40:
            if key == 'q':
                mode = 'main'
                options = MAIN_OPTIONS
                panels[LIST_PANEL].hide()
                panels[PROJ_PANEL].show()
                panels[TASK_PANEL].show()
                page = 0
                state = 0
            elif key == '-':
                page = refresh_active(windows, page-1)
            elif key == ' ':
                page = refresh_active(windows, page+1)
            else:
                page = refresh_active(windows, page)
                state = 40

        elif state == 50:
            if key == 'q':
                mode = 'main'
                options = MAIN_OPTIONS
                panels[LIST_PANEL].hide()
                panels[PROJ_PANEL].show()
                panels[TASK_PANEL].show()
                page = 0
                state = 0
            elif key == '-':
                page = refresh_all(windows, page-1)
            elif key == ' ':
                page = refresh_all(windows, page+1)
            else:
                page = refresh_all(windows, page)
                state = 50

        elif state == 60:
            if key == 'q':
                mode = 'main'
                options = MAIN_OPTIONS
                panels[LIST_PANEL].hide()
                panels[PROJ_PANEL].show()
                panels[TASK_PANEL].show()
                page = 0
                state = 0
            elif key == '-':
                page = refresh_deleted(windows, page-1)
            elif key == ' ':
                page = refresh_deleted(windows, page+1)
            else:
                page = refresh_deleted(windows, page)
                state = 60

        elif state == 70:
            if key == 'q':
                mode = 'main'
                options = MAIN_OPTIONS
                panels[LIST_PANEL].hide()
                panels[PROJ_PANEL].show()
                panels[TASK_PANEL].show()
                page = 0
                state = 0
            elif key == '-':
                page = refresh_all_open(windows, page-1)
            elif key == ' ':
                page = refresh_all_open(windows, page+1)
            else:
                page = refresh_all_open(windows, page)
                state = 70

        elif state == 80:
            if key == 'q':
                mode = 'main'
                options = MAIN_OPTIONS
                panels[LIST_PANEL].hide()
                panels[PROJ_PANEL].show()
                panels[TASK_PANEL].show()
                page = 0
                state = 0
            elif key == '-':
                page = refresh_states(windows, page-1)
            elif key == ' ':
                page = refresh_states(windows, page+1)
            else:
                page = refresh_states(windows, page)
                state = 80

    return

#-- link to main
def dbsui_main():
    DBG = Debug()
    curses.wrapper(dbsui)
    DBG.done()
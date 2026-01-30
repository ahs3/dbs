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
VERSION = "0.6.2"
YEAR = "2023"
AUTHOR = "Al Stone <ahs3@ahs3.net>"
CONFIG = "config"
CONFIG_VALUES = {}
REPO = "repo"
ACTIVE = "active"
OPEN = "open"
DONE = "done"
DELETED = "deleted"
ALLOWED_STATES = [ACTIVE, OPEN, DONE, DELETED]
DAYS_LIMIT = 60
LASTNUM = "lastnum"

#-- task fields
RE_NAME = re.compile('^Name:')
RE_TASK = re.compile('^Task:')
RE_STATE = re.compile('^State:')
RE_PROJECT = re.compile('^Project:')
RE_PRIORITY = re.compile('^Priority:')
RE_NOTE = re.compile('^Note:')

#-- config field
RE_REPO = re.compile('^repo:')

HIGH = 'h'
MEDIUM = 'm'
LOW = 'l'

RED_ON = "\033[38;5;9m"
GREEN_ON = "\033[38;5;10m"
YELLOW_ON = "\033[38;5;11m"
COLOR_OFF = "\033[0m"

#-- classes
class Task:
    def __init__(self):
        self.name = 0
        self.task = ""
        self.project = ""
        self.priority = "m"
        self.state = "open"
        self.notes = []

    def __lt__(self, other):
        return int(self.name) < int(other.name)

    def validate(self, info):
        # info needs to be an array of lines
        ret = ''
        linenum = 0
        for ii in info:
            line = ii.strip()
            k = line.split(':')[0]
            v = ' '.join(line.split(':')[1:]).strip()
            linenum += 1
            if RE_NAME.search(line) or RE_NOTE.search(line):
                continue
            elif RE_TASK.search(line):
                if len(v) > 0:
                    continue
                else:
                    ret = '? no task description at line %d' % (linenum)
            elif RE_PROJECT.search(line):
                if len(v) > 0:
                    continue
                else:
                    ret = '? no project name at line %d' % (linenum)
            elif RE_STATE.search(line):
                if v in ALLOWED_STATES:
                    continue
                else:
                    ret = '? unknown state "%s" at line %d' % (k, linenum)
            elif RE_PRIORITY.search(line):
                if v in [HIGH, MEDIUM, LOW]:
                    continue
                else:
                    ret = '? unknown priority "%s" at line %d' % (k, linenum)
            else:
                ret = '? unknown keyword "%s" at line %d' % (k, linenum)
                break
        return ret

    def set_fields(self, info):
        # info needs to be an array of lines
        ret = ''
        linenum = 0

        self.notes.clear()
        for ii in info:
            line = ii.strip()
            d = ' '.join(line.split(':')[1:])
            if RE_NAME.search(line):
                 num = line.replace('Name:','').strip()
                 self.name = task_canonical_name(num)
            elif RE_TASK.search(line):
                 self.task = line.replace('Task:','').strip()
            elif RE_STATE.search(line):
                 self.state = line.replace('State:','').strip()
            elif RE_PROJECT.search(line):
                 self.project = line.replace('Project:','').strip()
            elif RE_PRIORITY.search(line):
                 self.priority = line.replace('Priority:','').strip()
            elif RE_NOTE.search(line):
                 self.notes.append(line.replace('Note:','').strip())
        return

    def populate(self, fname, name):
        fd = open(fname, "r")
        info = fd.readlines()
        #print(info)
        fd.close()

        self.name = task_canonical_name(name)
        for ii in info:
            line = ii.strip()
            d = ' '.join(line.split(':')[1:])
            if RE_TASK.search(line):
                 self.task = line.replace('Task:','').strip()
            elif RE_STATE.search(line):
                 self.state = line.replace('State:','').strip()
            elif RE_PROJECT.search(line):
                 self.project = line.replace('Project:','').strip()
            elif RE_PRIORITY.search(line):
                 self.priority = line.replace('Priority:','').strip()
            elif RE_NOTE.search(line):
                 self.notes.append(line.replace('Note:','').strip())
        return

    def set_name(self, name):
        self.name = task_canonical_name(name)

    def get_name(self):
        return self.name

    def set_task(self, task):
        self.task = task

    def get_task(self):
        return self.task

    def set_project(self, project):
        self.project = project

    def get_project(self):
        return self.project

    def set_priority(self, priority):
        pri = priority.lower()
        if pri in [HIGH, MEDIUM, LOW]: 
            self.priority = pri

    def get_priority(self):
        return self.priority

    def set_state(self, state):
        s = state.lower()
        if s in ALLOWED_STATES:
            self.state = s

    def get_state(self):
        return self.state

    def add_note(self, note):
        today = datetime.date.today()
        txt = "(" + today.strftime("%Y-%m-%d") + ") " + note
        self.notes.append(txt)

    def get_notes(self):
        return self.notes

    def note_count(self):
        return len(self.notes)

    def dump(self):
        # for debug use
        print("--- file name: %s" % 
              os.path.join(dbs_repo(), self.state, self.name))
        print("Task: %s" % self.task)
        print("State: %s" % self.state)
        print("Project: %s" % self.project)
        print("Priority: %s" % self.priority)
        if len(self.notes) > 0:
            for ii in self.notes:
                print("Note: %s" % ii)
        return

    def show_text(self):
        text = "Name: %s\n" % self.name
        text += "Task: %s\n" % self.task
        text += "State: %s\n" % self.state
        text += "Project: %s\n" % self.project
        text += "Priority: %s\n" % self.priority
        if len(self.notes) > 0:
            for ii in self.notes:
                text += "Note: %s\n" % ii
        return text

    def print(self):
        print("%s--- file:%s %s" % (GREEN_ON, COLOR_OFF,
              os.path.join(dbs_repo(), self.state, self.name)))
        print("    %sTask:%s %s" % (GREEN_ON, COLOR_OFF, self.task))
        print("   %sState:%s %s" % (GREEN_ON, COLOR_OFF, self.state))
        print(" %sProject:%s %s" % (GREEN_ON, COLOR_OFF, self.project))
        print("%sPriority:%s %s" % (GREEN_ON, COLOR_OFF, self.priority))
        if len(self.notes) > 0:
            for ii in self.notes:
                print("    %sNote:%s %s" % (GREEN_ON, COLOR_OFF, ii))
        return

    def one_line(self):
        if self.priority == HIGH:
            color = RED_ON
        elif self.priority == MEDIUM:
            color = GREEN_ON
        else:
            color = ''

        note_cnt = len(self.notes)
        nnotes = ''
        if note_cnt > 0:
            nnotes = " [%d]" % note_cnt
        info = fix_task(self.task + nnotes)
        print(f'{color}{int(self.name):>8}    {self.priority:1}    {self.project:<8}   {info}{COLOR_OFF}')
        return

    def write(self, overwrite=False):
        fname = os.path.join(dbs_repo(), self.state, self.name)
        if not overwrite and os.path.isfile(fname):
            print("? task %s already exists" % self.name)
            sys.exit(1)
        fd = open(fname, "w")
        fd.write("Task: %s\n" % self.task)
        fd.write("State: %s\n" % self.state)
        fd.write("Project: %s\n" % self.project)
        fd.write("Priority: %s\n" % self.priority)
        if len(self.notes) > 0:
            for ii in self.notes:
                fd.write("Note: %s\n" % ii)
        fd.close()
        return

    def move(self, new_state):
        if new_state not in ALLOWED_STATES:
            print("? \"%s\" is not an allowed state" % new_state)
            sys.exit(1)
        fname = os.path.join(dbs_repo(), new_state, self.name)
        if os.path.isfile(fname):
            print("? task %s already exists" % self.name)
            sys.exit(1)
        fd = open(fname, "w")
        fd.write("Task: %s\n" % self.task)
        fd.write("State: %s\n" % new_state)
        fd.write("State: %s\n" % self.state)
        fd.write("Project: %s\n" % self.project)
        fd.write("Priority: %s\n" % self.priority)
        if len(self.notes) > 0:
            for ii in self.notes:
                fd.write("Note: %s\n" % ii)
        fd.close()
        return

#-- helper functions
def dbs_repo():
    global CONFIG_VALUES

    if CONFIG_VALUES[REPO]:
        return CONFIG_VALUES[REPO]
    else:
        return os.path.join(os.getenv("HOME"), '.config', 'dbs')

def dbs_config_name():
    return os.path.join(os.getenv("HOME"), '.config', 'dbs', CONFIG)

def dbs_open_name():
    return os.path.join(dbs_repo(), OPEN)

def dbs_done_name():
    return os.path.join(dbs_repo(), DONE)

def dbs_active_name():
    return os.path.join(dbs_repo(), ACTIVE)

def dbs_deleted_name():
    return os.path.join(dbs_repo(), DELETED)

def dbs_data_dirs_exist():
    if os.path.isdir(dbs_open_name()) and os.path.isdir(dbs_done_name()) and \
       os.path.isdir(dbs_active_name()) and os.path.isdir(dbs_deleted_name()):
        return True
    return False

def dbs_defconfig():
    fname = dbs_config_name()
    fd = open(fname, "w")
    fd.write("# default config file for dbs\n")
    fd.write("repo: %s\n" % dbs_repo())
    fd.close()
    return

def dbs_read_config():
    global CONFIG_VALUES

    fname = dbs_config_name()
    fd = open(fname, "r")
    for ii in fd.readlines():
        line = ii.strip()
        if RE_REPO.search(line):
            fields = line.split(':')
            CONFIG_VALUES[REPO] = fields[1].strip()
    fd.close()
    return

def dbs_make_data_dirs():
    if not os.path.isdir(dbs_open_name()):
        os.mkdir(dbs_open_name())
    if not os.path.isdir(dbs_done_name()):
        os.mkdir(dbs_done_name())
    if not os.path.isdir(dbs_active_name()):
        os.mkdir(dbs_active_name())
    if not os.path.isdir(dbs_deleted_name()):
        os.mkdir(dbs_deleted_name())
    return

def dbs_make_repo():
    print("dbs repo not found, creating defaults in %s" % dbs_repo())
    os.mkdir(dbs_repo())
    dbs_make_data_dirs()
    return

def dbs_next():
    # assuming task names are numbers, get the next unused number
    lnumpath = os.path.join(dbs_repo(), LASTNUM)
    if os.path.exists(lnumpath):
        fd = open(lnumpath, "r")
        data = fd.readline()
        fd.close()
    if len(data) > 1:
        n = int(data.strip())
    else:
        n = 1
    fd = open(lnumpath, "w")
    fd.seek(0)
    lnum = task_canonical_name(n)

    while task_name_exists(lnum):
        n = n + 1
        lnum = task_canonical_name(n)

    fd.write("%d\n" % n)
    fd.close()
    return lnum

def fix_task(info):
    # munge up the task string if it's longer than one line
    # NB: all the lengths and stuff are figured out by hand
    prefix_len = 28
    cnt = len(info)
    termsize = shutil.get_terminal_size()
    avail = termsize.columns - prefix_len
    last = 0
    res = ''
    while cnt > 0:
        #print('[a]', last, cnt, avail)
        #print('[a]', res)
        if cnt <= avail:
           res += info[last:]
           break
        else:
           t1 = info[last:last + avail]
           ii = t1.rfind(' ')
           t2 = info[last:last + ii]
           res += t2
           last = ii + 1
           cnt -= ii
           if cnt > 0:
               res += '\n' + "                            "

    return res

def get_last_modified_time(fullpath):
    fname = pathlib.Path(fullpath)
    stat = fname.stat()
    mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
    mstr = mtime.strftime("%Y-%m-%d %H:%M:%S")

    tzS, tzD = time.tzname
    if time.daylight:
        tz = " " + tzD
    else:
        tz = " " + tzS

    return mstr + tz

def get_task(name):
    fullpath = task_name_exists(name)
    if not fullpath:
        print("? task \"%s\" is not defined" % name)
        return None

    t = Task()
    t.populate(fullpath, name)
    return t

def list_tasks(state, add_space=False):
    if state not in ALLOWED_STATES:
        print("? unknown task state requested")
        sys.exit(1)

    fullpath = os.path.join(dbs_repo(), state)
    tasks = {}
    task_cnt = 0
    for (dirpath, dirnames, filenames) in os.walk(fullpath):
        for ii in filenames:
           t = Task()
           t.populate(os.path.join(fullpath, ii), ii)
           tasks[ii] = t

    if len(tasks) < 1:
        print("No %s tasks found." % state)
        return
    task_cnt += len(tasks)

    if add_space:
        print("")
    print("%s tasks:" % state.capitalize())
    one_line_header()
    keys = tasks.keys()
    for pri in [HIGH, MEDIUM, LOW]:
        for ii in sorted(keys):
           if tasks[ii].get_priority() == pri:
                tasks[ii].one_line()

    print_tasks_found(task_cnt)
    return

def one_line_header():
    print("-Name---  -Pri-  -Proj---  -Task---------------------------------")
    return

def print_projects_found(count, space=True):
    suffix = ''
    if count > 1:
        suffix = 's'
    if space:
        print("")
    print("%d project%s found." % (count, suffix))
    return

def print_tasks_found(count, space=True):
    suffix = ''
    if count > 1:
        suffix = 's'
    if space:
        print("")
    print("%d task%s found." % (count, suffix))
    return

def put_task(task, overwrite=True):
    task.write(overwrite=overwrite)
    return

def task_name_exists(name):
    if not name:
        return None

    cname = task_canonical_name(name)
    for state in [ACTIVE, OPEN, DONE, DELETED]:
        fullpath = os.path.join(dbs_repo(), state)
        for (dirpath, dirnames, filenames) in os.walk(fullpath):
            if cname in filenames:
                return os.path.join(dbs_repo(), state, cname)
    return None

def task_canonical_name(name):
    if not name:
        return None

    return f'{int(name):08d}'


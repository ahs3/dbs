#!/usr/bin/env python3
# Copyright (c) 2021, Al Stone <ahs3@ahs3.net>
#
#	dbs == dain-bread simple, a todo list for minimalists
#
# SPDX-License-Identifier: GPL-2.0-only
#

import collections
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

import dbs_task
from dbs_task import *

#-- globals
DO_PREFIX = re.compile('^do_')

#-- helper functions
def usage():
    print("usage: dbs <command> [<parameters>]")
    print("   defined commands:")
    cmdlist = []
    for ii in globals().keys():
        if DO_PREFIX.search(str(ii)):
            cmd = ii.replace('do_', '')
            cmdlist.append(cmd)

    for ii in sorted(cmdlist):
        print("      %s\t=> %s" % (ii, globals()[ii + "_help"]()))

    return

#-- command functions
def LA_help():
    return "list ALL tasks in any state"
    
def do_LA(params):
    list_tasks(ACTIVE)
    list_tasks(OPEN, add_space=True)
    list_tasks(DONE, add_space=True)
    return

def LD_help():
    return "list deleted tasks"
    
def do_LD(params):
    list_tasks(DELETED)
    return

def active_help():
    return "mark one or more tasks active: <name> ..."
    
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
    return "add open task: <name> <project> <priority> <description>"
    
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
    return "delete one or more tasks: <name> ..."
    
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
    return "mark one or more tasks done: <name> ..."
    
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
    return "lower the priority of a task: <name> ..."
    
def do_down(params):
    if len(params) < 1:
        print("? must provide at least one task name")
        sys.exit(1)
    
    for ii in params:
        t = get_task(ii)
        if not t:
            continue
        pri = t.get_priority()
        if pri == 'h':
            pri = 'm'
        elif pri == 'm':
            pri = 'l'
        else:
            print("? task \"%s\" already at 'l'" % ii)
            continue
        t.set_priority(pri)
        t.add_note("downed priority")
        put_task(t)

    return

def dup_help():
    return "duplicate a task: <old-name> <new-name>"
    
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
    return "edit a task: <name>"
    
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

def help_help():
    return "print this list"
    
def do_help(params):
    usage()
    return

def inactive_help():
    return "move one or more tasks from active to open: <name> ..."

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

def init_help():
    return "create initial dbs repository for tasks"

def do_init(params):
    if not os.path.isfile(dbs_config_name()):
        dbs_defconfig()
    dbs_read_config()
    
    if not os.path.isdir(dbs_repo()):
        dbs_make_repo()
    
    if not dbs_data_dirs_exist():
        dbs_make_data_dirs()

    return

def la_help():
    return "list active tasks"
    
def do_la(params):
    list_tasks(ACTIVE)
    return

def ld_help():
    return "list tasks done"
    
def do_ld(params):
    list_tasks(DONE)
    return

def lo_help():
    return "list open tasks"
    
def do_lo(params):
    list_tasks(OPEN)
    return

def log_help():
    return "log done task: <name> <project> <priority> <description>"
    
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

def lp_help():
    return "list open tasks for a project: <project>"
    
def do_lp(params):
    if len(params) < 1:
        print("? project name is required")
        sys.exit(1)

    project = params[0]
    task_cnt = 0

    tasks = {}
    fullpath = os.path.join(dbs_repo(), ACTIVE)
    for (dirpath, dirnames, filenames) in os.walk(fullpath):
    	for ii in filenames:
           t = Task()
           t.populate(os.path.join(fullpath, ii), ii)
           if t.get_project() == project:
               tasks[ii] = t

    if len(tasks) < 1:
        print("No active tasks found for project %s." % project)
    else:
        print("Active tasks for project %s:" % project)
        one_line_header()
        keys = tasks.keys()
        for pri in ['h', 'm', 'l']:
            for ii in sorted(keys):
               if tasks[ii].get_priority() == pri:
                    tasks[ii].one_line()
        task_cnt += len(tasks)

    tasks = {}
    fullpath = os.path.join(dbs_repo(), OPEN)
    for (dirpath, dirnames, filenames) in os.walk(fullpath):
    	for ii in filenames:
           t = Task()
           t.populate(os.path.join(fullpath, ii), ii)
           if t.get_project() == project:
               tasks[ii] = t

    if len(tasks) < 1:
        print("No open tasks found for project %s." % project)
        return
    else:
        print("")
        print("Open tasks for project %s:" % project)
        one_line_header()
        keys = tasks.keys()
        for pri in ['h', 'm', 'l']:
            for ii in sorted(keys):
               if tasks[ii].get_priority() == pri:
                    tasks[ii].one_line()
        task_cnt += len(tasks)

    print_tasks_found(task_cnt)
    return

def next_help():
    return "return next unused sequence number (to use as a name)"

def do_next(params):
    print("Next usable sequence number: %s" % dbs_next())
    return

def note_help():
    return "add a note to a task: <name> <note>"
    
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
    return "print project task counts"
    
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
    return "print project task summaries by priority"
    
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
                   summaries[proj] = { 'h':0, 'm':0, 'l':0, \
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
               summaries[ii]['h'], summaries[ii]['m'], summaries[ii]['l'],
               summaries[ii]['h'] + summaries[ii]['m'] + summaries[ii]['l']
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
    return "print project task summaries"
    
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
                   summaries[proj] = { 'h':0, 'm':0, 'l':0, \
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
               summaries[ii]['h'], summaries[ii]['m'], summaries[ii]['l'],
               summaries[ii]['h'] + summaries[ii]['m'] + summaries[ii]['l']
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
    return "list all tasks done or touched in <n> days: <n>"
    
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
        for pri in ['h', 'm', 'l']:
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
        for pri in ['h', 'm', 'l']:
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
        for pri in ['h', 'm', 'l']:
            for ii in sorted(keys):
               if tasks[ii].get_priority() == pri:
                    tasks[ii].one_line()
    return

def show_help():
    return "print out a single task: <name>"
    
def do_show(params):
    fullpath = task_name_exists(params[0])
    if not fullpath:
        print("? task \"%s\" is not defined" % params[0])
        sys.exit(1)

    t = get_task(params[0])
    t.print()

    print("")
    mtime = get_last_modified_time(fullpath)
    print("%sLast Modified:%s %s" % (GREEN_ON, COLOR_OFF, mtime))
    return

def state_help():
    return "print project task summaries by state"
    
def do_state(params):
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
                   summaries[proj] = { 'h':0, 'm':0, 'l':0, \
                                       ACTIVE:0, OPEN:0, DONE:0 }
               summaries[proj][pri] += 1
               summaries[proj][state] += 1
               tasks[ii] = t

    if len(tasks) < 1:
        print("No projects and no summaries.")
        return

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

def todo_help():
    return "print info for only projects with open tasks"
    
def do_todo(params):
    summaries = {}
    tasks = {}

    for state in ALLOWED_STATES:
        if state == DELETED or state == DONE:
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
                   summaries[proj] = { 'h':0, 'm':0, 'l':0, \
                                       ACTIVE:0, OPEN:0, DONE:0 }
               summaries[proj][pri] += 1
               summaries[proj][state] += 1
               tasks[ii] = t

    if len(tasks) < 1:
        print("No projects and no summaries.")
        return

    print("Summary by state:")
    print("-Name---  -Active- -Open-  --Total--")
    for ii in sorted(summaries.keys()):
        print("%s%-8s%s    %3d     %3d     %5d" %
            (GREEN_ON, ii, COLOR_OFF,
             summaries[ii][ACTIVE], summaries[ii][OPEN],
             summaries[ii][ACTIVE] + summaries[ii][OPEN]
            ))

    print("")
    if len(summaries.keys()) > 1:
        ssuffix = 's'
    if len(tasks) > 1:
        tsuffix = 's'
    print("%d project%s with %d task%s" % (len(summaries.keys()), ssuffix,
          len(tasks), tsuffix))

    return

def up_help():
    return "raise the priority of a task: <name> ..."
    
def do_up(params):
    if len(params) < 1:
        print("? must provide at least one task name")
        sys.exit(1)
    
    for ii in params:
        t = get_task(ii)
        if not t:
            continue
        pri = t.get_priority()
        if pri == 'l':
            pri = 'm'
        elif pri == 'm':
            pri = 'h'
        else:
            print("? task \"%s\" already at 'h'" % ii)
            continue
        t.set_priority(pri)
        t.add_note("upped priority")
        put_task(t)

    return

def version_help():
    return "print the current version of dbs"
    
def do_version(params):
    print("dbs, v%s -- the dain-bread simple TODO list" % VERSION)
    print("Copyright (c) %s, %s" % (YEAR, AUTHOR))
    return

#-- main
def dbs():
    if len(sys.argv) < 2:
        usage()
        sys.exit(0)
    else:
        params = ''
        if len(sys.argv) > 2:
            params = sys.argv[2:]
        cmd = 'do_' + sys.argv[1]

        if cmd not in globals():
            print("? no such command: %s" % sys.argv[1])
            sys.exit(1)

        if cmd != "do_init":
            do_init(params)

        globals()[cmd](params)

    return

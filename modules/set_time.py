#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  set_time.py
#
#  Copyright 2020 Thomas Castleman <contact@draugeros.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#
"""Set system time"""
from os import symlink, remove, devnull
from sys import stderr, argv
from subprocess import check_call, CalledProcessError


def eprint(*args, **kwargs):
    """Make it easier for us to print to stderr"""
    print(*args, file=stderr, **kwargs)


def _link(location):
    """Set time zone and localtime. Also, enable NTP sync."""
    remove("/etc/localtime")
    symlink("/usr/share/zoneinfo/%s" % (location), "/etc/localtime")
    remove("/etc/timezone")
    with open("/etc/timezone", "w+") as timezone:
        timezone.write(location)
    try:
        check_call(["timedatectl", "set-ntp", "true"], stdout=devnull,
                   stderr=devnull)
    except CalledProcessError:
        pass



def set_time(time_zone):
    """Set time zone and hardware clock"""
    _link(time_zone)
    # removed setting hardware clock because this function is supposed to be
    # run on a seperate machine from what the IMG file will be installed to


if __name__ == '__main__':
    set_time(argv[1])

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  set_locale.py
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
"""Set system locale for a given langauage name"""
from __future__ import print_function
from sys import argv, stderr
from os import remove, devnull
from subprocess import check_call

def eprint(*args, **kwargs):
    """Make it easier for us to print to stderr"""
    print(*args, file=stderr, **kwargs)

def set_locale(locale, output):
    """Handle setting locale for a given locale code"""
    # Edit /etc/locale.gen
    with open("/etc/locale.gen", "r") as gen_file:
        contents = gen_file.read()
    contents = contents.split("\n")
    for each in enumerate(contents):
        if contents[each[0]] == ("# " + locale + " UTF-8"):
            contents[each[0]] = locale + " UTF-8"
            break
    remove("/etc/locale.gen")
    contents = "\n".join(contents)
    with open("/etc/locale.gen", "w+") as new_gen:
        new_gen.write(contents)
    check_call(["locale-gen"], stdout=output, stderr=output)
    check_call(["update-locale", "LANG=%s" % (locale), "LANGUAGE"],
               stdout=output, stderr=output)


if __name__ == '__main__':
    set_locale(argv[1])

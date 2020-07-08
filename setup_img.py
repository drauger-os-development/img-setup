#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  setup_img.py
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
"""Setup IMG files for installation on a variety of ARM computers"""
from os import chroot, fchdir, O_RDONLY, chdir, path, close, getuid, getcwd, listdir, getenv, remove
from os import open as get
from shutil import move, copyfile
from subprocess import check_call, CalledProcessError
from sys import argv, stderr
from sys import exit as leave
from getpass import getpass
from copy import deepcopy
import json
import re
import urllib3
import modules

R = "\033[0;31m"
G = "\033[0;32m"
Y = "\033[1;33m"
BOLD = "\033[1m"
RESET = "\033[0m"
VERSION = "0.0.1-alpha1"
HELP = """setup.py, Version %s
\t-d, --debug\t\tUse debugging mode to see errors and other output
\t-h, --help\t\tPrint this help dialog and exit.
\t-v,--version\t\tPrint current version and exit.

Simply run this program without any arguments and it will handle the rest."""

def __mount__(device):
    """Mount device at path
    It would be much lighter weight to use ctypes to do this
    But, that keeps throwing an 'Invalid Argument' error.
    Calling Mount with check_call is the safer option.
    """
    try:
        check_call(["mount", "-t", "auto", "-o", "loop", device, "/mnt"],
                   stdout=devnull, stderr=devnull)
    except CalledProcessError as error:
        eprint(R + BOLD + "COULD NOT MOUNT " + device + RESET)
        eprint(error)

def __chroot_mount__(device, path_dir, fstype="", options=""):
    """Mount necessary psudeo-filesystems"""
    if device == "/run":
        try:
            check_call(["mount", device, path_dir, "--bind"], stdout=devnull,
                       stderr=devnull)
        except CalledProcessError:
            pass
    else:
        try:
            check_call(["mount", device, path_dir, "-t", fstype, "-o", options],
                       stdout=devnull, stderr=devnull)
        except CalledProcessError:
            pass

def __unmount__(path_dir):
    """unmount psudeo-filesystems"""
    try:
        check_call(["umount", path_dir], stdout=devnull, stderr=devnull)
    except CalledProcessError:
        try:
            check_call(["umount", "-l", path_dir], stdout=devnull,
                       stderr=devnull)
        except CalledProcessError:
            pass


def __update__(percentage):
    print("\r %s %%" % (percentage), end="")

def arch_chroot(path_dir):
    """replicate arch-chroot functionality in Python"""
    real_root = get("/", O_RDONLY)
    if path_dir[len(path_dir) - 1] == "/":
        path_dir = path_dir[0:len(path_dir) - 2]
    __chroot_mount__("proc", path_dir + "/proc", "proc", "nosuid,noexec,nodev")
    __chroot_mount__("sys", path_dir + "/sys", "sysfs",
                     "nosuid,noexec,nodev,ro")
    if path.exists(path_dir + "/sys/firmware/efi/efivars"):
        __chroot_mount__("efivars", path_dir + "/sys/firmware/efi/efivars",
                         "efivarfs", "nosuid,noexec,nodev")
    __chroot_mount__("udev", path_dir + "/dev", "devtmpfs", "mode=0755,nosuid")
    __chroot_mount__("devpts", path_dir + "/dev/pts",
                     "devpts", "mode=0620,gid=5,nosuid,noexec")
    __chroot_mount__("shm", path_dir + "/dev/shm", "tmpfs",
                     "nosuid,noexec,nodev")
    __chroot_mount__("/run", path_dir + "/run")
    __chroot_mount__("tmp", path_dir + "/tmp", "tmpfs",
                     "mode=1777,strictatime,nodev,nosuid")
    chdir(path_dir)
    chroot(path_dir)
    return real_root

def de_chroot(real_root, path_dir):
    """exit chroot from arch_chroot()"""
    __unmount__(path_dir + "/proc")
    __unmount__(path_dir + "/sys")
    if path.exists(path_dir + "/sys/firmware/efi/efivars"):
        __unmount__(path_dir + "/sys/firmware/efi/efivars")
    __unmount__(path_dir + "/dev")
    __unmount__(path_dir + "/dev/pts")
    __unmount__(path_dir + "/dev/shm")
    __unmount__(path_dir + "/run")
    __unmount__(path_dir + "/tmp")
    fchdir(real_root)
    chroot(".")
    close(real_root)

def check_internet():
    """Check Internet Connectivity"""
    try:
        urllib3.connection_from_url('https://draugeros.org', timeout=1)
        return True
    except:
        return False
    return False

def has_special_character(input_string):
    """Check for special characters"""
    regex = re.compile(r'[@_!#$%^&*()<>?/\|}{~:]')
    if regex.search(input_string) is None:
        return False
    return True

def hasspace(input_string):
    """Check for spaces"""
    for each3 in input_string:
        if each3.isspace():
            return True
    return False

def get_device(config):
    """Get device IMG will be installed to"""
    print(G + BOLD + "DEVICE SELECTION" + RESET)
    print("------")
    while True:
        print(BOLD + "Supported devices:" + RESET)
        print(G + BOLD + "GREEN" + RESET + " is for tested and known working. " + R + BOLD + "RED" + RESET + " is for working state unknown or not working.")
        for each in config:
            print(BOLD + config[each][0] + ": " + RESET, end="")
            count = 0
            for each1 in config[each][1]:
                if count == 6:
                    print("")
                    count = 0
                if config[each][1][each1]:
                    print(G + each1 + RESET, end=", ")
                else:
                    print(R + each1 + RESET, end=", ")
                count = count + 1
            print("")
        device = input(G + BOLD + "Which device is yours?: " + RESET).lower()
        for each in config:
            if device in config[each][1]:
                return config[each][2]
        print(R + BOLD + "\nDEVICE NOT FOUND. PLEASE TRY AGAIN.\n" + RESET)

def get_username():
    """get username"""
    print(G + BOLD + "USERNAME SETUP" + RESET)
    print("------")
    while True:
        username = input("What do you want the username to be?: ").lower()
        if has_special_character(username):
            eprint(R + BOLD + "Special Characters Not Allowed" + RESET)
        elif hasspace(username):
            eprint(R + BOLD + "Spaces Not Allowed" + RESET)
        else:
            break
    return username


def get_passwd():
    """get password"""
    print(G + BOLD + "PASSWORD SETUP" + RESET)
    print(Y + BOLD + "PASSWORD HIDDEN FOR YOUR PROTECTION" + RESET)
    print("------")
    while True:
        password = getpass("What do you want the password to be?: ")
        password_conf = getpass("Repeat password: ")
        if password != password_conf:
            eprint(R + BOLD + "PASSWORDS DO NOT MATCH" + RESET)
        else:
            password_conf = ""
            break
    return password

def get_hostname():
    """get hostname"""
    print(G + BOLD + "COMPUTER NAME" + RESET)
    print("------")
    while True:
        hostname = input("What do you want your computer to be named?: ").lower()
        if has_special_character(hostname):
            eprint(R + BOLD + "Special Characters Not Allowed" + RESET)
        elif hasspace(hostname):
            eprint(R + BOLD + "Spaces Not Allowed" + RESET)
        else:
            break
    return hostname


def get_updates():
    """get whether the user wants install updates or not"""
    print(G + BOLD + "UPDATE SETTINGS" + RESET)
    print("------")
    updates = input("Do you want to make install updates in the IMG file (if you are on an AMD64 computer, select 'no')? [Y/n]: ").lower()
    return bool(updates in ("y", "yes"))


def get_autologin():
    """get autologin settings"""
    print(G + BOLD + "AUTOLOGIN SETTINGS" + RESET)
    print("------")
    autologin = input("Do you want to enable autologin? [Y/n]: ").lower()
    return bool(autologin in ("y", "yes"))

def get_lang():
    """Get language settings"""
    locales = None
    locale = None
    print(G + BOLD + "LANGUAGE SETTINGS" + RESET)
    print("------")
    answer = input("Would you like the IMG file to use the same lanaguage as this computer? [Y/n]: ").lower()
    if answer in ("yes", "y"):
        return getenv("LANG")
    print("Parsing language options . . .")
    with open("/etc/locale.gen", "r") as locale_file:
        data = locale_file.read()
    data = data.split("\n")
    for each in range(len(data) - 1, -1, -1):
        if "UTF-8" not in data[each][-5:]:
            del data[each]
            continue
        data[each] = data[each].split(" ")
        if data[each][0] == "#":
            data[each] = data[each][1][:-6]
        else:
            data[each] = data[each][0][:-6]
    for each in range(len(data) - 1, -1, -1):
        if (("@" in data[each]) or ("_" not in data[each])):
            del data[each]
    while True:
        locales = deepcopy(data)
        while True:
            print("Which locale is yours?")
            for each in enumerate(locales):
                print("[%s] %s" % (each[0], locales[each[0]]))
            answer = input("Locale number or name (or 'filter' to filter): ")
            if answer.lower() == "filter":
                answer = input("Search term: ")
                for each in range(len(locales) - 1, -1, -1):
                    if answer not in locales[each]:
                        del locales[each]
            else:
                break
            if len(locales) == 0:
                eprint(R + "No matching options." + RESET)
                continue
        try:
            locale = locales[int(answer)]
            break
        except IndexError:
            eprint(R + "Not a valid locale number. Please try again." + RESET)
        except (TypeError, ValueError):
            for each in locales:
                if answer.lower() == each.lower():
                    locale = each
                    break
            if locales is None:
                eprint(R + "Not a valid locale. Please try again." + RESET)
            else:
                break
    return "%s.UTF-8" % (locale)


def get_keyboard():
    """Get keyboard settings"""
    # print(G + BOLD + "KEYBOARD SETTINGS" + RESET)
    # print("------")
    return ("Do not configure keyboard; keep kernel keymap", "", "")


def get_time_zone():
    """Get keyboard settings"""
    region = None
    subregion = None
    print(G + BOLD + "TIME SETTINGS" + RESET)
    print("------")
    while True:
        print(G + "REGION" + RESET)
        zones = ["Africa", "America", "Antarctica", "Arctic", "Asia",
                 "Atlantic", "Australia", "Brazil", "Canada", "Chile",
                 "Europe", "Indian", "Mexico", "Pacific", "US"]
        print("Which region is yours?")
        for each in enumerate(zones):
            print("[%s] %s" % (each[0], zones[each[0]]))
        answer = input("Region number or name: ")
        try:
            region = zones[int(answer)]
            break
        except IndexError:
            eprint(R + "Not a valid region number. Please try again." + RESET)
        except (TypeError, ValueError):
            for each in zones:
                if answer.lower() == each.lower():
                    region = each
                    break
            if region is None:
                eprint(R + "Not a valid region. Please try again." + RESET)
            else:
                break
    while True:
        print(G + "SUBREGION" + RESET)
        zones = sorted(listdir("/usr/share/zoneinfo/" + region))
        while True:
            print("Which subregion is yours?")
            for each in enumerate(zones):
                print("[%s] %s" % (each[0], zones[each[0]]))
            answer = input("Region number or name (or 'filter' to filter): ")
            if answer.lower() == "filter":
                answer = input("Search term: ")
                for each in range(len(zones) - 1, -1, -1):
                    if answer not in zones[each]:
                        del zones[each]
            else:
                break
            if len(zones) == 0:
                eprint(R + "No matching options." + RESET)
                break
        if len(zones) == 0:
            continue
        try:
            subregion = zones[int(answer)]
            break
        except IndexError:
            eprint(R + "Not a valid region number. Please try again." + RESET)
        except (TypeError, ValueError):
            for each in zones:
                if answer.lower() == each.lower():
                    subregion = each
                    break
            if subregion is None:
                eprint(R + "Not a valid subregion. Please try again." + RESET)
            else:
                break
    return region + "/" + subregion


def setup(config):
    """Perform setup process"""
    print(BOLD + "Setup process initited\n" + RESET)
    settings = {"INTERNET":True}
    settings["bootloader package"] = get_device(config)
    print("")
    settings["USERNAME"] = get_username()
    print("")
    settings["PASSWORD"] = get_passwd()
    print("")
    settings["COMPUTER_NAME"] = get_hostname()
    print("")
    settings["UPDATES"] = get_updates()
    print("")
    settings["LOGIN"] = get_autologin()
    print("")
    # need to figure out langauge, keyboard model/layout/varient, and time zone
    # settings obtaining
    settings["TIME_ZONE"] = get_time_zone()
    print("")
    settings["LANG"] = get_lang()
    print("")
    keyboard = get_keyboard()
    settings["MODEL"] = keyboard[0]
    settings["LAYOUT"] = keyboard[1]
    settings["VARIANT"] = keyboard[2]
    print("")
    print(G + BOLD + "IMG FILE LOCATION" + RESET)
    print("------")
    while True:
        location = input("Where is the IMG file to be set up located (do not use environment variables like $HOME)?: ")
        if location[0] == "~":
            location = path.expanduser(location)
        if path.isfile(location):
            break
        eprint(R + BOLD + "NOT A VALID FILE PATH TO IMG FILE" + RESET)
    print("")
    settings["FILE_DESC"] = devnull
    configuration_procedure(settings, location)


def configuration_procedure(settings, location):
    """Perform the actual IMG configuration"""
    __update__(2)
    __mount__(location)
    __update__(6)
    location = getcwd() + "/modules"
    file_list = listdir(location)
    for each in file_list:
        if ((each == "__pycache__") or (".py" in each)):
            continue
        copyfile(location + "/" + each, "/mnt/" + each)
    __update__(7)
    move("/mnt/etc/resolv.conf", "/mnt/etc/resolv.conf.save")
    copyfile("/etc/resolv.conf", "/mnt/etc/resolv.conf")
    __update__(8)
    try:
        if settings["LANG"] in ("", None):
            print("\r")
            eprint("LANG is not set. Defaulting to environment variable $LANG")
            settings["LANG"] = getenv("LANG")
    except KeyError:
        print("\r")
        eprint("LANG is not set. Defaulting to environment variable $LANG")
        settings["LANG"] = getenv("LANG")
    try:
        if settings["TIME_ZONE"] in ("", None):
            print("\r")
            eprint("TIME_ZONE is not set. Defaulting to /etc/timezone setting")
            with open("/etc/timezone", "r") as tzdata:
                settings["TIME_ZONE"] = tzdata.read()[0:-1]
    except KeyError:
        print("\r")
        eprint("TIME_ZONE is not set. Defaulting to /etc/timezone setting")
        with open("/etc/timezone", "r") as tzdata:
            settings["TIME_ZONE"] = tzdata.read()[0:-1]
    try:
        if settings["USERNAME"] in ("", None):
            print("\r")
            eprint("USERNAME NOT SET")
            settings["USERNAME"] = get_username()
    except KeyError:
        print("\r")
        eprint("USERNAME NOT SET")
        settings["USERNAME"] = get_username()
    try:
        if settings["COMPUTER_NAME"] in ("", None):
            print("\r")
            eprint("COMP_NAME is not set. Defaulting to drauger-system-installed")
            settings["COMPUTER_NAME"] = "drauger-system-installed"
    except KeyError:
        print("\r")
        eprint("COMP_NAME is not set. Defaulting to drauger-system-installed")
        settings["COMPUTER_NAME"] = "drauger-system-installed"
    try:
        if settings["PASSWORD"] in ("", None):
            print("\r")
            eprint("PASSWORD NOT SET")
            settings["PASSWORD"] = get_passwd()
    except KeyError:
        print("\r")
        eprint("PASSWORD NOT SET")
        settings["PASSWORD"] = get_passwd()
    try:
        if settings["UPDATES"] in ("", None):
            print("\r")
            eprint("UPDATES is not set. Defaulting to false.")
            settings["UPDATES"] = False
    except KeyError:
        print("\r")
        eprint("UPDATES is not set. Defaulting to false.")
        settings["UPDATES"] = False
    try:
        if settings["MODEL"] in ("", None):
            print("\r")
            eprint("KEYBOARD MODEL is not set, defaulting to kernel keymap")
            settings["MODEL"] = "Do not configure keyboard; keep kernel keymap"
    except KeyError:
        settings["MODEL"] = "Do not configure keyboard; keep kernel keymap"
    try:
        if ((settings["LAYOUT"] in ("", None)) and (settings["MODEL"] != "Do not configure keyboard; keep kernel keymap")):
            print("\r")
            eprint("KEYBOARD LAYOUT is not set, defaulting to English (US)")
            settings["LAYOUT"] = "English (US)"
    except KeyError:
        settings["LAYOUT"] = "English (US)"
    try:
        if ((settings["VARIENT"] in ("", None)) and (settings["MODEL"] != "Do not configure keyboard; keep kernel keymap")):
            print("\r")
            eprint("KEYBOARD VARIENT is not set, defaulting to English (US)")
            settings["VARIENT"] = "English (US)"
    except KeyError:
        settings["VARIENT"] = "English (US)"
    __update__(14)
    chdir("/mnt")
    real_root = arch_chroot("/mnt")
    __update__(19)
    modules.master.install(settings, True)
    de_chroot(real_root, "/mnt")
    print(Y + BOLD + "CLEANING UP . . . " + RESET)
    for each in file_list:
        try:
            remove("/mnt/" + each)
        except FileNotFoundError:
            pass
    remove("/mnt/etc/resolv.conf")
    move("/mnt/etc/resolv.conf.save", "/mnt/etc/resolv.conf")
    __unmount__("/mnt")
    print(G + BOLD + "IMG SETUP COMPLETE!" + RESET)


def download_config():
    """Download JSON config"""
    print("Downloading Package Configuration . . .")
    http = urllib3.PoolManager()
    return json.loads(http.request("GET", "https://raw.githubusercontent.com/drauger-os-development/img-setup/master/bootloaders.json").data)


def eprint(*args, **kwargs):
    """Make it easier for us to print to stderr"""
    print(*args, file=stderr, **kwargs)

def run():
    """Do the thing"""
    if getuid() != 0:
        print("setup_img.py is not running as root. Would you like to exit now, or elevate to root here?")
        choice = input("exit or elevate: ").lower()
        if choice == "elevate":
            argv.insert(0, "sudo")
            leave(check_call(argv))
        else:
            print("Exiting . . .")
            leave(0)
    try:
        config = download_config()
    except:
        eprint("Your internet is either slow or non-existant. Internet is necessary for setup. Please try again later.")
        leave(2)
    setup(config)

if __name__ == '__main__':
    if len(argv) > 1:
        if argv[1] in ("-h", "--help"):
            print(HELP)
        elif argv[1] in ("-v", "--version"):
            print(VERSION)
        elif argv[1] in ("-d", "--debug"):
            from subprocess import PIPE as devnull
            run()
    else:
        from subprocess import DEVNULL as devnull
        run()

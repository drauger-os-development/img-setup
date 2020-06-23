#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  master.py
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
"""
Configure newly installed system from within a chroot
"""
from __future__ import print_function
from sys import argv, stderr
from subprocess import Popen, PIPE, check_output, check_call, CalledProcessError
import multiprocessing
from os import remove, mkdir, environ, symlink, chmod, listdir, path
from shutil import rmtree, copyfile
from inspect import getfullargspec
from time import sleep
import json
import urllib3
import warnings


# import our own programs
import modules.auto_login_set as auto_login_set
import modules.set_time as set_time
import modules.systemd_boot_config as systemd_boot_config
import modules.set_locale as set_locale

def eprint(*args, **kwargs):
    """Make it easier for us to print to stderr"""
    print(*args, file=stderr, **kwargs)

def __update__(percentage):
    print("\r %s %%" % (percentage), end="")

class MainInstallation():
    """Main Installation Procedure, minus low-level stuff"""
    def __init__(self, processes_to_do, settings):
        for each1 in processes_to_do:
            process_new = getattr(MainInstallation, each1, self)
            args_list = getfullargspec(process_new)[0]
            args = []
            for each in args_list:
                args.append(settings[each])
            globals()[each1] = multiprocessing.Process(target=process_new, args=args)
            globals()[each1].start()
        percent = 80 / len(processes_to_do)
        growth = 80 / len(processes_to_do)
        while len(processes_to_do) > 0:
            for each in range(len(processes_to_do) - 1, -1, -1):
                if not globals()[processes_to_do[each]].is_alive():
                    globals()[processes_to_do[each]].join()
                    del processes_to_do[each]
                    __update__(percent)
                    percent = percent + growth

    def time_set(TIME_ZONE):
        """Set system time"""
        set_time.set_time(TIME_ZONE)

    def locale_set(LANG):
        """Set system locale"""
        set_locale.set_locale(LANG)

    def set_networking(COMPUTER_NAME):
        """Set system hostname"""
        eprint("Setting hostname to %s" % (COMPUTER_NAME))
        try:
            remove("/etc/hostname")
        except FileNotFoundError:
            pass
        with open("/etc/hostname", "w+") as hostname:
            hostname.write(COMPUTER_NAME)
        try:
            remove("/etc/hosts")
        except FileNotFoundError:
            pass
        with open("/etc/hosts", "w+") as hosts:
            hosts.write("127.0.0.1 %s" % (COMPUTER_NAME))

    def make_user(USERNAME, PASSWORD):
        """Set up main user"""
        # This needs to be set up in Python. Leave it in shell for now
        try:
            Popen(["/make_user.sh", USERNAME, PASSWORD])
        except PermissionError:
            chmod("/make_user.sh", 0o777)
            Popen(["/make_user.sh", USERNAME, PASSWORD])

    def __install_updates__(UPDATES, INTERNET):
        """Install updates"""
        if ((UPDATES) and (INTERNET)):
            try:
                check_call("/install_updates.sh")
            except PermissionError:
                chmod("/install_updates.sh", 0o777)
                check_call("/install_updates.sh")
        elif not INTERNET:
            eprint("Cannot install updates. No internet.")

    def apt(UPDATES, INTERNET):
        """Run commands for apt sequentially to avoid front-end lock"""
        MainInstallation.__install_updates__(UPDATES, INTERNET)

    def set_passwd(PASSWORD):
        """Set Root password"""
        process = Popen("chpasswd", stdout=stderr.buffer, stdin=PIPE, stderr=PIPE)
        process.communicate(input=bytes(r"root:%s" % (PASSWORD), "utf-8"))

    def lightdm_config(LOGIN, USERNAME):
        """Set autologin setting for lightdm"""
        auto_login_set.auto_login_set(LOGIN, USERNAME)

    def set_keyboard(MODEL, LAYOUT, VARIENT):
        """Set keyboard model, layout, and varient"""
        with open("/usr/share/X11/xkb/rules/base.lst", "r") as xkb_conf:
            kcd = xkb_conf.read()
        kcd = kcd.split("\n")
        for each1 in enumerate(kcd):
            kcd[each1[0]] = kcd[each1[0]].split()
        try:
            remove("/etc/default/keyboard")
        except FileNotFoundError:
            pass
        xkbm = ""
        xkbl = ""
        xkbv = ""
        for each1 in kcd:
            if " ".join(each1[1:]) == MODEL:
                xkbm = each1[0]
            elif " ".join(each1[1:]) == LAYOUT:
                xkbl = each1[0]
            elif " ".join(each1[1:]) == VARIENT:
                xkbv = each1[0]
        with open("/etc/default/keyboard", "w+") as xkb_default:
            xkb_default.write("""XKBMODEL=\"%s\"
XKBLAYOUT=\"%s\"
XKBVARIANT=\"%s\"
XKBOPTIONS=\"\"

BACKSPACE=\"guess\"
""" % (xkbm, xkbl, xkbv))
        Popen(["udevadm", "trigger", "--subsystem-match=input",
               "--action=change"], stdout=stderr.buffer)

def set_plymouth_theme():
    """Ensure the plymouth theme is set correctly"""
    Popen(["update-alternatives", "--install",
           "/usr/share/plymouth/themes/default.plymouth",
           "default.plymouth",
           "/usr/share/plymouth/themes/drauger-theme/drauger-theme.plymouth",
           "100", "--slave",
           "/usr/share/plymouth/themes/default.grub", "default.plymouth.grub",
           "/usr/share/plymouth/themes/drauger-theme/drauger-theme.grub"],
          stdout=stderr.buffer)
    process = Popen(["update-alternatives", "--config",
                     "default.plymouth"], stdout=stderr.buffer, stdin=PIPE,
                    stderr=PIPE)
    process.communicate(input=bytes("2\n", "utf-8"))


def _install_bootloader_package(package):
    """Install bootloader package

    Package should be the package name of the bootloader
    """
    check_call(["apt", "install", package])


def install_bootloader(bootloader):
    """Determine whether bootloader needs to be systemd-boot (for UEFI) or GRUB (for BIOS)
    and install the correct one.
    """
    if "grub" in bootloader:
        _install_bootloader_package(bootloader)
        _install_grub()
    elif bootloader in ("u-boot-rockchip", "u-boot-rpi", "u-boot-tegra"):
        _install_bootloader_package(bootloader)


def _install_grub():
    """set up and install GRUB.
    This function is only retained for BIOS systems.
    """
    check_call(["grub-mkdevicemap", "--verbose"], stdout=stderr.buffer)
    check_call(["grub-mkconfig", "-o", "/boot/grub/grub.cfg"],
               stdout=stderr.buffer)
    check_call(["grub-mkstandalone", "--verbose", "--force",
                "--format=arm64-efi", "--output=/boot/efi/bootx64.efi"],
               stdout=stderr.buffer)


def setup_lowlevel(bootloader, root):
    """Set up kernel and bootloader"""
    release = check_output(["uname", "--release"]).decode()[0:-1]
    set_plymouth_theme()
    eprint("\n\t###\tMAKING INITRAMFS\t###\t")
    check_call(["mkinitramfs", "-o", "/boot/initrd.img-" + release], stdout=stderr.buffer)
    install_bootloader(bootloader)
    sleep(0.5)
    symlink("/boot/initrd.img-" + release, "/boot/initrd.img")
    symlink("/boot/vmlinuz-" + release, "/boot/vmlinuz")


def make_num(string):
    try:
        return int(string)
    except ValueError:
        return float(string)


def install(settings, internet):
    """Entry point for installation procedure"""
    processes_to_do = dir(MainInstallation)
    for each in range(len(processes_to_do) - 1, -1, -1):
        if processes_to_do[each][0] == "_":
            del processes_to_do[each]
    MainInstallation(processes_to_do, settings)
    setup_lowlevel(settings["bootloader package"])

if __name__ == "__main__":
    # get length of argv
    ARGC = len(argv)
    # set vars
    # for security reasons, these are no longer environmental variables
    SETTINGS = json.loads(argv[1])
    # settings["LANG"] = argv[1]
    # settings["TIME_ZONE"] = argv[2]
    # settings["USERNAME"] = argv[3]
    # settings["PASSWORD"] = argv[4]
    # settings["COMPUTER_NAME"] = argv[5]
    # settings["EXTRAS"] = bool(int(argv[6]))
    # settings["UPDATES"] = bool(int(argv[7]))
    # settings["EFI"] = argv[8]
    # settings["ROOT"] = argv[9]
    # settings["LOGIN"] = bool(int(argv[10]))
    # settings["MODEL"] = argv[11]
    # settings["LAYOUT"] = argv[12]
    # settings["VARIENT"] = argv[13]
    INTERNET = check_internet()

    install(SETTINGS, INTERNET)

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
        percent = 50 / len(processes_to_do)
        growth = 50 / len(processes_to_do)
        while len(processes_to_do) > 0:
            for each in range(len(processes_to_do) - 1, -1, -1):
                if not globals()[processes_to_do[each]].is_alive():
                    globals()[processes_to_do[each]].join()
                    del processes_to_do[each]
                    __update(percent)
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

    def remove_launcher(USERNAME):
        """Remove system installer desktop launcher"""
        try:
            remove("/home/%s/Desktop/system-installer.desktop" % (USERNAME))
        except FileNotFoundError:
            try:
                rmtree("/home/%sE/.config/xfce4/panel/launcher-3" % (USERNAME))
            except FileNotFoundError:
                eprint("Cannot find launcher for system-installer. User will need to remove manually.")

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


def install_bootloader(bootloader, root, release):
    """Determine whether bootloader needs to be systemd-boot (for UEFI) or GRUB (for BIOS)
    and install the correct one.
    """
    if bootloader == "systemd-boot":
        _install_systemd_boot(release, root)
    elif "grub" in bootloader:
        _install_bootloader_package(bootloader)
        _install_grub(root)
    elif bootloader in ("u-boot-rockchip", "u-boot-rpi", "u-boot-tegra"):
        _install_bootloader_package(bootloader)


def _install_grub(root):
    """set up and install GRUB.
    This function is only retained for BIOS systems.
    """
    root = list(root)
    for each1 in range(len(root) - 1, -1, -1):
        try:
            int(root[each1])
            del root[each1]
        except ValueError:
            break
    if root[-1] == "p":
        del root[-1]
    root = "".join(root)
    check_call(["grub-mkdevicemap", "--verbose"], stdout=stderr.buffer)
    check_call(["grub-install", "--verbose", "--force", "--target=i386-pc",
                root], stdout=stderr.buffer)
    check_call(["grub-mkconfig", "-o", "/boot/grub/grub.cfg"],
               stdout=stderr.buffer)

def _install_systemd_boot(release, root):
    """set up and install systemd-boot"""
    try:
        mkdir("/boot/efi")
    except FileExistsError:
        pass
    mkdir("/boot/efi/loader")
    mkdir("/boot/efi/loader/entries")
    mkdir("/boot/efi/Drauger_OS")
    environ["SYSTEMD_RELAX_ESP_CHECKS"] = "1"
    with open("/etc/environment", "a") as envi:
        envi.write("export SYSTEMD_RELAX_ESP_CHECKS=1")
    try:
        check_call(["bootctl", "--path=/boot/efi", "install"], stdout=stderr.buffer)
    except CalledProcessError as e:
        eprint("WARNING: bootctl issued CalledProcessError:")
        eprint(e)
        eprint("Performing manual installation of systemd-boot.")
        try:
            mkdir("/boot/efi/EFI")
        except FileExistsError:
            pass
        try:
            mkdir("/boot/efi/EFI/systemd")
        except FileExistsError:
            pass
        try:
            mkdir("/boot/efi/EFI/BOOT")
        except FileExistsError:
            pass
        try:
            mkdir("/boot/efi/EFI/Linux")
        except FileExistsError:
            pass
        try:
            copyfile("/usr/lib/systemd/boot/efi/systemd-bootx64.efi", "/boot/efi/EFI/BOOT/BOOTX64.EFI")
        except FileExistsError:
            pass
        try:
            copyfile("/usr/lib/systemd/boot/efi/systemd-bootx64.efi", "/boot/efi/EFI/systemd/systemd-bootx64.efi")
        except FileExistsError:
            pass
    with open("/boot/efi/loader/loader.conf", "w+") as loader_conf:
        loader_conf.write("default Drauger_OS\ntimeout 5\neditor 1")
    try:
        check_call(["chattr", "-i", "/boot/efi/loader/loader.conf"], stdout=stderr.buffer)
    except CalledProcessError:
        eprint("CHATTR FAILED ON loader.conf, setting octal permissions to 444")
        chmod("/boot/efi/loader/loader.conf", 0o444)
    systemd_boot_config.systemd_boot_config(root)
    check_call("/etc/kernel/postinst.d/zz-update-systemd-boot", stdout=stderr.buffer)
    check_systemd_boot(release, root)


def setup_lowlevel(efi, root):
    """Set up kernel and bootloader"""
    release = check_output(["uname", "--release"]).decode()[0:-1]
    set_plymouth_theme()
    eprint("\n\t###\tMAKING INITRAMFS\t###\t")
    check_call(["mkinitramfs", "-o", "/boot/initrd.img-" + release], stdout=stderr.buffer)
    install_bootloader(efi, root, release)
    sleep(0.5)
    symlink("/boot/initrd.img-" + release, "/boot/initrd.img")
    symlink("/boot/vmlinuz-" + release, "/boot/vmlinuz")

def check_systemd_boot(release, root):
    """Ensure systemd-boot was configured correctly"""
    # Initialize variables
    root_flags = "quiet splash"
    recovery_flags = "ro recovery nomodeset"
    # Get Root UUID
    uuid = check_output(["blkid", "-s", "PARTUUID", "-o", "value", root]).decode()[0:-1]

    # Check for standard boot config
    if not path.exists("/boot/efi/loader/entries/Drauger_OS.conf"):
        # Write standard boot conf if it doesn't exist
        eprint("Standard Systemd-boot entry non-existant")
        try:
            with open("/boot/efi/loader/entries/Drauger_OS.conf", "w+") as main_conf:
                main_conf.write("""title   Drauger OS
linux   /Drauger_OS/vmlinuz
initrd  /Drauger_OS/initrd.img
options root=PARTUUID=%s %s""" % (uuid, root_flags))
            eprint("Made standard systemd-boot entry")
        # Raise an exception if we cannot write the entry
        except (PermissionError, IOError):
            eprint("\t###\tERROR\t###\tCANNOT MAKE STANDARD SYSTEMD-BOOT ENTRY CONFIG FILE\t###ERROR\t###\t")
            raise IOError("Cannot make standard systemd-boot entry config file. Installation will not boot.")
    else:
        eprint("Standard systemd-boot entry checks out")
    # Check for recovery boot config
    if not path.exists("/boot/efi/loader/entries/Drauger_OS_Recovery.conf"):
        eprint("Recovery Systemd-boot entry non-existant")
        try:
            # Write recovery boot conf if it doesn't exist
            with open("/boot/efi/loader/entries/Drauger_OS_Recovery.conf", "w+") as main_conf:
                main_conf.write("""title   Drauger OS Recovery
linux   /Drauger_OS/vmlinuz
initrd  /Drauger_OS/initrd.img
options root=PARTUUID=%s %s""" % (uuid, recovery_flags))
            eprint("Made recovery systemd-boot entry")
        # Raise a warning if we cannot write the entry
        except (PermissionError, IOError):
            eprint("\t###\WARNING\t###\tCANNOT MAKE RECOVERY SYSTEMD-BOOT ENTRY CONFIG FILE\t###WARNING\t###\t")
            warnings.warn("Cannot make recovery systemd-boot entry config file. Installation will not be recoverable.")
    else:
        eprint("Recovery systemd-boot entry checks out")

    # Make sure we have our kernel image, config file, initrd, and System map
    files = listdir("/boot")
    vmlinuz = []
    config = []
    initrd = []
    sysmap = []
    # Sort the files by name
    for each in files:
        if "vmlinuz-" in each:
            vmlinuz.append(each)
        elif "config-" in each:
            config.append(each)
        elif "initrd.img-" in each:
            initrd.append(each)
        elif "System.map-" in each:
            sysmap.append(each)

    # Sort the file names by version number.
    # The file with the highest index in the list is the latest version
    vmlinuz = sorted(vmlinuz)[-1]
    config = sorted(config)[-1]
    initrd = sorted(initrd)[-1]
    sysmap = sorted(sysmap)[-1]
    # Copy the latest files into place
    # Also, rename them so that systemd-boot can find them
    if not path.exists("/boot/efi/Drauger_OS/vmlinuz"):
        eprint("vmlinuz non-existant")
        copyfile("/boot/" + vmlinuz, "/boot/efi/Drauger_OS/vmlinuz")
        eprint("vmlinuz copied")
    else:
        eprint("vmlinuz checks out")
    if not path.exists("/boot/efi/Drauger_OS/config"):
        eprint("config non-existant")
        copyfile("/boot/" + config, "/boot/efi/Drauger_OS/config")
        eprint("config copied")
    else:
        eprint("Config checks out")
    if not path.exists("/boot/efi/Drauger_OS/initrd.img"):
        eprint("initrd.img non-existant")
        copyfile("/boot/" + initrd, "/boot/efi/Drauger_OS/initrd.img")
        eprint("initrd.img copied")
    else:
        eprint("initrd.img checks out")
    if not path.exists("/boot/efi/Drauger_OS/System.map"):
        eprint("System.map non-existant")
        copyfile("/boot/" + sysmap, "/boot/efi/Drauger_OS/System.map")
        eprint("System.map copied")
    else:
        eprint("System.map checks out")




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
    setup_lowlevel(settings["EFI"], settings["ROOT"], settings["bootloader package"])

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
    # if ARGC == 15:
        # settings["SWAP"] = argv[14]
    # else:
        # settings["SWAP"] = None
    INTERNET = check_internet()

    install(SETTINGS, INTERNET)

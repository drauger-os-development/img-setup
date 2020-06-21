# img-setup
IMG file set up for ARM64-based computers

This code is not used to MAKE IMG files. It is used to modify pre-existing IMG files to be useful on a larger variety of ARM computers. Making it so that essentially only one (1) IMG file needs to be distributed for many different ARM computers.

**This program is a CLI application only. There is no GUI.**

setup.py
---

This script is supposed to be run to set up the IMG file. Linux and MacOS have Python support out of the box.
If you are on Windows, there is no guarentee this will work on your computer.


bootloaders.json
---

This file is used to determine what bootloader packages are needed for what devices. This file is not shipped with the IMG file, unlike setup.py.
Instead, the latest version is downloaded at execution time.

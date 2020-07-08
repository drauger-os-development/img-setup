#!/bin/bash
# -*- coding: utf-8 -*-
#
#  make_user.sh
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
USERNAME="$1"
PASSWORD="$2"
output="$3"
if [ "$output" == "" ]; then
	{
		#change live user to $USERNAME
		usermod -l "$USERNAME" live 2>/dev/null 1>/dev/null
		groupmod -n "$USERNAME" live 2>/dev/null 1>/dev/null
		#change refrences from old home to new
		sed -i "s:/home/live:/home/$USERNAME:g" /home/live/.config/gtk-3.0/bookmarks 2>/dev/null 1>/dev/null
		#rename home directory
		mv /home/live /home/"$USERNAME" 2>/dev/null 1>/dev/null
		sed -i "s/live/$USERNAME/g" /etc/passwd  2>/dev/null 1>/dev/null
	} || {
		useradd --create-home --system --shell /bin/bash --groups adm,cdrom,sudo,audio,dip,plugdev,lpadmin "$USERNAME" 2>/dev/null 1>/dev/null
	}
	#change password
	builtin echo "$USERNAME:$PASSWORD" | chpasswd 2>/dev/null 1>/dev/null
else
	{
		#change live user to $USERNAME
		usermod -l "$USERNAME" live
		groupmod -n "$USERNAME" live
		#change refrences from old home to new
		sed -i "s:/home/live:/home/$USERNAME:g" /home/live/.config/gtk-3.0/bookmarks
		#rename home directory
		mv /home/live /home/"$USERNAME"
		sed -i "s/live/$USERNAME/g" /etc/passwd
	} || {
		useradd --create-home --system --shell /bin/bash --groups adm,cdrom,sudo,audio,dip,plugdev,lpadmin "$USERNAME"
	}
	#change password
	builtin echo "$USERNAME:$PASSWORD" | chpasswd
fi


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
function fix_home () 
{
	{
		USERNAME="$1"
		if [ -d /home/home/live ]; then
			mv -v /home/home/live /home/"$USERNAME"
			rm -vrf /home/home
		fi
	} 1>&2
}

#change live user to $USERNAME
usermod -l "$USERNAME" live 1>&2
groupmod -n "$USERNAME" live 1>&2
if $(ls /home | grep -q "$USERNAME"); then
	#check to see if the user has a home folder already. 
	rm -rfv /home/live 1>&2
elif [ -d /home/home/live ]; then
	fix_home "$USERNAME"
else
	#change refrences from old home to new
	sed -i "s:/home/live:/home/$USERNAME:g" /home/live/.config/gtk-3.0/bookmarks 1>&2
	#rename home directory
	mv -v /home/live /home/"$USERNAME" 1>&2 || fix_home "$USERNAME"
fi
sed -i "s/live/$USERNAME/g" /etc/passwd  1>&2
}
#change password
builtin echo "$USERNAME:$PASSWORD" | chpasswd


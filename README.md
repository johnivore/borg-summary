# borg-summary

## About

`borgsummary` is intended to assist systems administrators in checking if [borg backups](http://borgbackup.readthedocs.io/en/stable/index.html) are out of date, and printing a succinct summary of one or more borg backup repositories.  Because getting backup information from `borg list` can be slow for repositories with many backups, `borgsummary` stores backup data in a SQLite database.  It can do other little things as well, such as checking for backups overlapping each other in time, and creating tarballs of the most recent backups.


## Requirements

* Python 3.2+
* `tabulate`
* `sqlalchemy`


## Example usage - single repository

In this example, `/backup/borg` contains a single borg repository.

### Update the SQLite database with data about a borg repository

    borgsummary --update /backup/borg

### Print a warning if there have been no backups in a while

    borgsummary --check /backup/borg

### Print a summary of the borg repo


```
$ borgsummary --detail /backup/borg

Size of all backups: 164.0 GB

/backup/borg
------------

Command line: /usr/bin/borg create borgbackup@myhost.example.com:myhost.example.com::{hostname}-{now:%Y-%m-%dT%H:%M:%S.%f} /home /etc /var /root /usr/local --exclude-from /tmp/tmpuyxtd2rd

Actual size on disk: 47.0 GB

start                duration      # files    orig size (GB)    comp size (GB)    dedup size (GB)
-------------------  ----------  ---------  ----------------  ----------------  -----------------
2018-05-31 07:00:10  0:00:21         10419               0.4               0.4                0.1
2018-06-22 07:00:11  0:00:32         12931               0.7               0.7                0.2
2018-07-15 07:00:10  0:02:44         13024               1.3               1.3                0.1
2018-07-22 07:00:12  0:00:27         13923               1.4               1.4                0.1
2018-07-29 07:00:10  0:00:29         14303               1.5               1.5                0.1
```

### Example crontab

A simplified example run hourly checks to update the SQLite database, a daily check to ensure backups are running, and a weekly job to send a summary email.  Times are coordinated a bit to not run multiple jobs simultaneously.

```
30  * * * * root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --update /backup/borg
0  12 * * * root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --check /backup/borg | mail -E -s 'Warning: borg backup issues' root
45 12 * * 0 root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --detail /backup/borg | mail -s 'Borg backup summary' root
```


## Example usage - multiple repositories

You can use `borgsummary --all` to update, check, and print summaries about multiple borg repositories.  The directory hierarchy is expected to follow this structure:

```
/backup/borg
    /host1.example.com/one_backup
    /host1.example.com/another_backup
    /host2.example.com/whatever
```

This accommodates multiple clients with multiple borg backup repositories.

### Update the SQLite database with data about all repositories

    borgsummary --all --update /backup/borg

### Print a warning if any repo hasn't been backed up in a while

    borgsummary --all --check /backup/borg

### Print a summary of all repos

```
$ borgsummary --all --detail /backup/borg

Size of all backups: 164.0 GB

repo                                 last backup          duration      # files    # backups    size (GB)
-----------------------------------  -------------------  ----------  ---------  -----------  -----------
host1.example.com - one_backup       2019-01-12 07:00:09  0:00:41         13652           56         47.0
host1.example.com - another_backup   2019-01-10 05:00:09  0:00:11          9032           32          1.2
host2.example.com                    2019-01-12 00:39:57  0:00:49        219351           61        116.0
```

### Check for overlapping backups

```
$ borgsummary --all --check-overlap /backup/borg

Warning: some backups within the previous 3 days overlap:

repo 1             start 1              duration 1    repo 2             start 2              duration 2
-----------------  -------------------  ------------  -----------------  -------------------  ------------
host1.example.com  2019-01-20 04:00:16  0:01:41       host2.example.com  2019-01-20 04:00:11  0:00:53
host1.example.com  2019-01-21 04:00:16  0:01:43       host2.example.com  2019-01-21 04:00:10  0:00:36
host1.example.com  2019-01-22 04:00:16  0:01:41       host2.example.com  2019-01-22 04:00:13  0:00:52
```

### Print backup start times

(So you can try to schedule backups to overlap as little as possible)

```
$ borgsummary --all --start-times /backup/borg

Last backup start & end times:

repo                start    end
-----------------   -------  -----
host1.example.com   06:23    06:24
host2.example.com   07:00    07:00
```

### Make tarballs of all backups

For quick-and-dirty gzipped tarball creation, you can use `--tar-latest`:

    borg-summary --all --tar-latest /mnt/offsite /backup/borg

### Example crontab

```
40  * * * * root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --all --update /backup/borg
0  12 * * * root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --all --check /backup/borg | mail -E -s 'Warning: borg backup issues' root
50 12 * * 0 root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --all --detail /backup/borg | mail -s 'Borg backup summary' root
```


## Config file

The optional config file (follows XDG, usually `~/.config/borg-summary.conf`) can override the number of hours since the last backup that will trigger a warning with `--check`.  Use -1 to disable warnings altogether.

```ini
[/backup/borg/host1.example.com/host1.example.com]
warn_hours = -1

[/backup/borg/host2.example.com/host2.example.com]
warn_hours = 72
```


## License

```
Copyright 2019-2020  John Begenisich

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```

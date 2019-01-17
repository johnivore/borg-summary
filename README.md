# borg-summary

## About

`borgsummary` is intended to assist systems administrators in checking if [borg backups](http://borgbackup.readthedocs.io/en/stable/index.html) are out of date, and printing a succinct summary of one or more borg backup repositories.  Because getting backup information from `borg list` can be slow for repositories with many backups, `borgsummary` stores backup data in a SQLite database.


## Requirements

* Python 3.2+
* `tabulate`
* `sqlalchemy`


## Example usage

In this example, `/backup/borg` contains a single borg repository.

Update the SQLite database with data about a borg repository:

    borgsummary --update /backup/borg

Print a warning if there have been no backups in a while:

    borgsummary --check /backup/borg

Print a summary of the borg repo:

    borgsummary --detail /backup/borg

```
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
...
```


## Example crontab

A simplified example run hourly checks to update the SQLite database, a daily check to ensure backups are running, and a weekly job to send a summary email.  Times are coordinated a bit to not run multiple jobs simultaneously.

```
30  * * * * root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --update /backup/borg
0  12 * * * root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --check /backup/borg | mail -E -s 'Warning: borg backup issues' root
45 12 * * 0 root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --detail /backup/borg | mail -s 'Borg backup summary' root
```

## Using `--all`

You can use `borgsummary --all` to update, check, and print summaries about multiple borg repositories.  The directory hierarchy is expected to follow this structure:

```
/backup/borg
    /host1.example.com/one_backup
    /host1.example.com/another_backup
    /host2.example.com/whatever
```

This accommodates multiple clients with multiple borg backup repositories.

Update the SQLite database with data about all repositories:

    borgsummary --all --update /backup/borg

Print a warning if any repo hasn't been backed up in a while:

    borgsummary --all --check /backup/borg

Print a summary of all repos:

    borgsummary --all --detail /backup/borg

```
Size of all backups: 164.0 GB

repo                                 last backup          duration      # files    # backups    size (GB)
-----------------------------------  -------------------  ----------  ---------  -----------  -----------
host1.example.com - one_backup       2019-01-12 07:00:09  0:00:41         13652           56         47.0
host1.example.com - another_backup   2019-01-10 05:00:09  0:00:11          9032           32          1.2
host2.example.com                    2019-01-12 00:39:57  0:00:49        219351           61        116.0
...
```

### `--all` example crontab

```
30  * * * * root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --all --update /backup/borg
0  12 * * * root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --all --check /backup/borg | mail -E -s 'Warning: borg backup issues' root
45 12 * * 0 root /root/.virtualenvs/borgsummary/bin/python /root/borg-summary/borgsummary.py --all --detail /backup/borg | mail -s 'Borg backup summary' root
```

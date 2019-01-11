# borg-summary

## About

These scripts are intended to run on a backup server hosting multiple [borg backup](http://borgbackup.readthedocs.io/en/stable/index.html) repositories. It can:

* print a succinct summary of a borg repository
* print a summary of all backups in a borg repository
* print a warning if backup data for a borg repository is out of date
* print a warning if there hasn't been a backup in over 24 hours

Because getting backup information from `borg list` can be slow for repositories with many backups, `borgsummary` uses CSV files to store backup information.


## Requirements

* Python 3
* `tabulate`
* `sqlalchemy`


## Usage in cron

A simplified example of using `borgsummary.py --all` to run hourly checks to update the SQLite database, a daily check to ensure backups are running, and a weekly job to send a summary email:

```
@hourly root python3 /root/borg-summary/borgsummary.py --all --update /data/borg
@daily  root python3 /root/borg-summary/borgsummary.py --all --check /data/borg | mail -E -s 'Warning: borg backup issues' root
@weekly root python3 /root/borg-summary/borgsummary.py --all --detail /data/borg | mail -s 'Borg backup summary' root
```


## Borg pool structure

To use `borgsummary --all`, the directory hierarchy is expected to be:

```
/some/path/to/backups
    /host1.example.com/borgbackupA
    /host1.example.com/borgbackupB
    /host1.example.com/borgbackupN...
    /host2.example.com/borgbackupA
    ...
```

This "doubled" directory structure is to accommodate clients with multiple borg backup repositories.

Currently, `borgsummary --all` expects each host to have one backup set, with its name matching the client's hostname.

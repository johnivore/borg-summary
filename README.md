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
* `borgsummary-all` requires `tabulate`


## Usage in cron

A simplified example of using `borgsummary-all` to run hourly checks to update CSV data files, a daily check to ensure backups are running, and a weekly job to send a summary email:

```
@hourly root python3 /root/borg-summary/borgsummary-all.py --update /data/borg
@daily  root python3 /root/borg-summary/borgsummary-all.py --check /data/borg | mail -E -s 'Warning: borg backup issues' root
@weekly root python3 /root/borg-summary/borgsummary-all.py /data/borg | mail -s 'Borg backup summary' root
```


## Borg pool structure and CSV files

To use `borgsummary-all`, the directory hierarchy is expected to be:

```
/some/path/to/backups
    /host1.example.com/borgbackupA
    /host1.example.com/borgbackupB
    /host1.example.com/borgbackupN...
    /host2.example.com/borgbackupA
    ...
```

This "doubled" directory structure is to accommodate clients with multiple borg backup repositories.

Currently, `borgsummary` expects each host to have one backup set, with its name matching the client's hostname.



## Changelog

### [Unreleased]

#### Added

#### Changed

* Use borg's JSON "API" (`--json`).
* Instead of storing backup info in CSV files, store in a SQLite database using SQLAlchemy.

#### Removed


### [0.1]

#### Added

* Read & write CSV data files containing backup info for each host.
* Better error checking from borg output.
* Add `borgsummary-all` which prints a very succinct summary of all backup repos, and optionally details about every repo.

#### Changed

* Split into two scripts; `borgsummary` reports on just one borg backup; `borgsummary-all` is a wrapper script which handles multiple borg repos.
* Created BorgBackupRepo class to better encapsulate the data in a borg backup repo.

#### Removed

* Because it's no longer applicable, removed `--first` option.

### [Initial version]

* Prints a simple summary of multiple borg backup repositories.

# borg-summary

## About

These scripts are intended to run on a backup server hosting multiple [borg backup](http://borgbackup.readthedocs.io/en/stable/index.html) repositories. It can:

* print a succinct summary of a borg repository
* print a succinct list of all backups in a borg repository
* print a warning if backup data for a borg repository is out of date

Because getting backup information from `borg list` can be slow for repositories with many backups, `borgsummary` uses CSV files to store backup information.


## Requirements

* Python 3
* `borgsummary-all` requires `tabulate`


## Usage in cron

A simplified example of using `borgsummary` to run hourly checks to update CSV data files, a daily check to ensure backups are running, and a weekly job to send a summary email:

```
@daily  root python3 /root/borg-summary/borgsummary-all.py --check /data/borg | mail -E -s 'Warning: borg backup issues' root
@weekly root python3 /root/borg-summary/borgsummary-all.py /data/borg | mail -s 'Borg backup summary' root
@hourly root python3 /root/borg-summary/borgsummary-all.py --autoupdate /data/borg
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

* Read & write CSV data files containing backup info for each host.
* Better error checking from borg output.
* Add `borgsummary-all` which prints a very succinct summary of all backup repos, and optionally details about every repo.

#### Changed

* Split into two scripts; `borgsummary` reports on just one borg backup; `borgsummary-all` is a wrapper script which handles multiple borg repos.

#### Removed

* Because it's no longer applicable, removed `--first` option.

### Initial version

* Prints a simple summary of multiple borg backup repositories.

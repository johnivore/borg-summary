# borg-summary

## About

This script is intended to run on a backup server hosting multiple [borg backup](http://borgbackup.readthedocs.io/en/stable/index.html) repositories. It can:

* print a succinct summary of a borg repository
* print a succinct list of all backups in a borg repository
* print a warning if backup data for a borg repository is out of date

Because getting backup information from `borg list` can be slow for repositories with many backups, `borg-summary` uses CSV files to store backup information.


## Borg pool structure and CSV files

The directory hierarchy is expected to be:

```
/some/path/to/backups
    /host1.example.com/borgbackupA
    /host1.example.com/borgbackupB
    /host1.example.com/borgbackupN...
    /host2.example.com/borgbackupA
    ...
```

This "doubled" directory structure is to accommodate clients with multiple borg backup repositories.

If your borg backup structure does not conform to this, that's fine, but you will need to specify the

Currently, `borg-summary` expects each host to have one backup set, with its name matching the client's hostname.



## Changelog

### [Unreleased]

#### Added

* Read & write CSV data files containing backup info for each host.
* Better error checking from borg output.

#### Changed

* Split into two scripts; borg-summary.py reports on just one borg backup; borg-summary-all.py is a wrapper script which handles multiple borg repos.

#### Removed

* Because it's no longer applicable, removed --first option.

### Initial version

* Prints a simple summary of multiple borg backup repositories.

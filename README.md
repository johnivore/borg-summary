# borg-summary

## About

This script is intended to run on a backup server hosting multiple borg backup repositories.

It prints a succinct summary of borg backups for multiple backup repositories.

The directory hierarchy is expected to be:

```
/some/path/to/backups
  /host1.example.com/host1.example.com
  /host2.example.com/host2.example.com
  host3/host3
  ...
```

This "doubled" directory structure is because each host has its own repository to which it is restricted using SSH authorized keys ("key_options").  For each host there might be multiple backup repositories.  Currently, `borg-summary` just expects each host to have one backup set, with its name matching the client's hostname.

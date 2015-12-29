===== General =====
===================

This is a set of scripts for OpenLierox dedicated server.
The scripts are based on the original script set provided with OpenLierox,
but many parts have been rewritten.

These scripts have been developed and tested with OpenLierox 0.58 on Linux.
Other versions and platforms have not been tested.

For now, complete documentation is not available. Read the comments
and follow examples for more information.


===== Changes/new features =====
================================

- New team handling system

- New, simplified map/mod autocycler

- New voting system

- Various annoyance mitigation options


===== Configuration notes =====
===============================

- Compared to the original scripts, most game settings that can be set in
options.cfg are no longer set by the scripts, so they should be set
in options.cfg.

- The scripts itself are configured by editing dedicated_config.py, just
like the original scripts. However, mod presets are configured in 
dedicated_control_presets.py.

- By default, the main script assumes that all configuration scripts
are located in the same directory as the other scripts. 


===== Untested features =====
=============================

Some old features have not been tested after modifications, 
including but not limited to:

-Admin interface
-Manual team change
-Game modes other than deathmatch and team deathmatch
-DedServerWatcher script


===== Licensing =====
=====================

This software is provided under the same license as
the original scripts.

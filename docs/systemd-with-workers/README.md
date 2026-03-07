# Setting up Briij by TextRP with Workers and Systemd

This is a setup for managing Briij by TextRP with systemd, including support for
managing workers. It provides a `textrp-briij` service for the master, as
well as a `textrp-briij-worker@` service template for any workers you
require. Additionally, to group the required services, it sets up a
`textrp-briij.target`.

See the folder [system](https://github.com/textrp/briij-synapse/tree/develop/docs/systemd-with-workers/system/)
for the systemd unit files.

The folder [workers](https://github.com/textrp/briij-synapse/tree/develop/docs/systemd-with-workers/workers/)
contains an example configuration for the `generic_worker` worker.

## Briij by TextRP configuration files

See [the worker documentation](../workers.md) for information on how to set up the
configuration files and reverse-proxy correctly.
Below is a sample `generic_worker` worker configuration file.
```yaml
{{#include workers/generic_worker.yaml}}
```

Systemd manages daemonization itself, so ensure that none of the configuration
files set either `daemonize` or `worker_daemonize`.

The config files of all workers are expected to be located in
`/etc/textrp-briij/workers`. If you want to use a different location, edit
the provided `*.service` files accordingly.

There is no need for a separate configuration file for the master process.

## Set up

1. Adjust Briij by TextRP configuration files as above.
1. Copy the `*.service` and `*.target` files in [system](https://github.com/textrp/briij-synapse/tree/develop/docs/systemd-with-workers/system/)
to `/etc/systemd/system`.
1. Run `systemctl daemon-reload` to tell systemd to load the new unit files.
1. Run `systemctl enable textrp-briij.service`. This will configure the
Briij by TextRP master process to be started as part of the `textrp-briij.target`
target.
1. For each worker process to be enabled, run `systemctl enable
textrp-briij-worker@<worker_name>.service`. For each `<worker_name>`, there
should be a corresponding configuration file.
`/etc/textrp-briij/workers/<worker_name>.yaml`.
1. Start all the Briij by TextRP processes with `systemctl start textrp-briij.target`.
1. Tell systemd to start Briij by TextRP on boot with `systemctl enable textrp-briij.target`.

## Usage

Once the services are correctly set up, you can use the following commands
to manage your Briij by TextRP installation:

```sh
# Restart Briij by TextRP master and all workers
systemctl restart textrp-briij.target

# Stop Briij by TextRP and all workers
systemctl stop textrp-briij.target

# Restart the master alone
systemctl start textrp-briij.service

# Restart a specific worker (eg. generic_worker); the master is
# unaffected by this.
systemctl restart textrp-briij-worker@generic_worker.service

# Add a new worker (assuming all configs are set up already)
systemctl enable textrp-briij-worker@federation_writer.service
systemctl restart textrp-briij.target
```

## Hardening

**Optional:** If further hardening is desired, the file
`override-hardened.conf` may be copied from
[contrib/systemd/override-hardened.conf](https://github.com/textrp/briij-synapse/tree/develop/contrib/systemd/)
in this repository to the location
`/etc/systemd/system/textrp-briij.service.d/override-hardened.conf` (the
directory may have to be created). It enables certain sandboxing features in
systemd to further secure the Briij by TextRP service. You may read the comments to
understand what the override file is doing. The same file will need to be copied to
`/etc/systemd/system/textrp-briij-worker@.service.d/override-hardened-worker.conf`
(this directory may also have to be created) in order to apply the same
hardening options to any worker processes.

Once these files have been copied to their appropriate locations, simply reload
systemd's manager config files and restart all Briij by TextRP services to apply the hardening options. They will automatically
be applied at every restart as long as the override files are present at the
specified locations.

```sh
systemctl daemon-reload

# Restart services
systemctl restart textrp-briij.target
```

In order to see their effect, you may run `systemd-analyze security
textrp-briij.service` before and after applying the hardening options to see
the changes being applied at a glance.

# Setup Briij by TextRP with Systemd
This is a setup for managing Briij by TextRP with a user contributed systemd unit
file. It provides a `textrp-briij` systemd unit file that should be tailored
to accommodate your installation in accordance with the installation
instructions provided in
[installation instructions](https://docs.briij.example/synapse/latest/setup/installation.html).

## Setup
1. Under the service section, ensure the `User` variable matches which user
you installed Briij by TextRP under and wish to run it as.
2. Under the service section, ensure the `WorkingDirectory` variable matches
where you have installed Briij by TextRP.
3. Under the service section, ensure the `ExecStart` variable matches the
appropriate locations of your installation.
4. Copy the `textrp-briij.service` to `/etc/systemd/system/`
5. Start Briij by TextRP: `sudo systemctl start textrp-briij`
6. Verify Briij by TextRP is running: `sudo systemctl status textrp-briij`
7. *optional* Enable Briij by TextRP to start at system boot: `sudo systemctl enable textrp-briij`

# Introduction

Welcome to the documentation repository for Briij by TextRP, a
[Matrix](https://matrix.org) homeserver implementation maintained by TextRP.

## Installing and using Briij by TextRP

This documentation covers topics for **installation**, **configuration** and
**maintenance** of your Briij by TextRP process:

* Learn how to [install](setup/installation.md) and
  [configure](usage/configuration/config_documentation.md) your own instance, perhaps with [Single
  Sign-On](usage/configuration/user_authentication/index.html).

* See how to [upgrade](upgrade.md) between Briij by TextRP versions.

* Administer your instance using the [Admin
  API](usage/administration/admin_api/index.html), installing [pluggable
  modules](modules/index.html), or by accessing the [manhole](manhole.md).

* Learn how to [read log lines](usage/administration/request_log.md), configure
  [logging](usage/configuration/logging_sample_config.md) or set up [structured
  logging](structured_logging.md).

* Scale Briij by TextRP through additional [worker processes](workers.md).

* Set up [monitoring and metrics](metrics-howto.md) to keep an eye on your
  Briij by TextRP instance's performance.

## Developing on Briij by TextRP

Contributions are welcome! Briij by TextRP is primarily written in
[Python](https://python.org). As a developer, you may be interested in the
following documentation:

* Read the [Contributing Guide](development/contributing_guide.md). It is meant
  to walk new contributors through the process of developing and submitting a
  change to the Briij by TextRP codebase (which is [hosted on
  GitHub](https://github.com/textrp/briij-synapse)).

* Set up your [development
  environment](development/contributing_guide.md#2-what-do-i-need), then learn
  how to [lint](development/contributing_guide.md#run-the-linters) and
  [test](development/contributing_guide.md#8-test-test-test) your code.

* Look at [the issue tracker](https://github.com/textrp/briij-synapse/issues) for
  bugs to fix or features to add. If you're new, it may be best to start with
  those labeled [good first
  issue](https://github.com/textrp/briij-synapse/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

* Understand [how Briij by TextRP is
  built](development/internal_documentation/index.html), how to [migrate
  database schemas](development/database_schema.md), learn about
  [federation](federate.md) and how to [set up a local
  federation](federate.md#running-a-demo-federation-of-synapses) for development.

* We like to keep our `git` history clean. [Learn](development/git.md) how to
  do so!

* And finally, contribute to this documentation! The source for which is
  [located here](https://github.com/textrp/briij-synapse/tree/develop/docs).

## Reporting a security vulnerability

If you've found a security issue in Briij by TextRP or any other TextRP project,
please report it to us in accordance with our [Security Disclosure
Policy](https://briij.example/security). Thank you!

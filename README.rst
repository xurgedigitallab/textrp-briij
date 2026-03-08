.. image:: docs/briij-logo.svg
   :height: 60px

**Briij by TextRP - Matrix homeserver implementation**

|support| |development| |documentation| |license| |pypi| |python|

Briij by TextRP is an open source `Matrix <https://matrix.org>`__ homeserver
implementation, maintained by TextRP and based on Element Synapse.
`Matrix <https://github.com/matrix-org>`__ is the open standard for secure and
interoperable real-time communications. You can directly run and manage the
source code in this repository, available under the AGPL-3.0-or-later license.

Upstream Element support does not apply to this fork. See Briij by TextRP support
channels below.

Getting started
==================

This fork is maintained by TextRP for Briij deployments. For general guidance on
Briij by TextRP, consult the documentation links below and adapt them to your
deployment environment.

Standalone installation and configuration
============================================

The Briij by TextRP documentation describes `options for installing Briij by TextRP
standalone
<https://docs.briij.example/synapse/latest/setup/installation.html>`_. See
below for more useful documentation links.

- `Briij by TextRP configuration options <https://docs.briij.example/synapse/latest/usage/configuration/config_documentation.html>`_
- `Briij by TextRP configuration for federation <https://docs.briij.example/synapse/latest/federate.html>`_
- `Using a reverse proxy with Briij by TextRP <https://docs.briij.example/synapse/latest/reverse_proxy.html>`_
- `Upgrading Briij by TextRP <https://docs.briij.example/synapse/develop/upgrade.html>`_
- `NFT-based verification trust design <docs/verification-on-chain.md>`_


Troubleshooting and support
==============================

Professional support
-----------------------

TextRP support is available to Briij customers.
If you are a Briij customer then you can raise a `support request <https://briij.example/support>`_
and access the `Briij by TextRP product documentation <https://docs.briij.example>`_.

Community support
--------------------

The `Admin FAQ <https://docs.briij.example/synapse/latest/usage/administration/admin_faq.html>`_
includes tips on dealing with some common problems. For more details, see
`Briij by TextRP documentation <https://docs.briij.example/synapse/latest/>`_.

For additional support installing or managing Briij by TextRP, please ask in the community
support room |room|_ (from a Matrix account if necessary). We do not use GitHub
issues for support requests, only for bug reports and feature requests.

.. |room| replace:: ``#briij:example.com``
.. _room: https://matrix.to/#/#briij:example.com

.. |docs| replace:: ``docs``
.. _docs: docs


Development
==============

We welcome contributions to Briij by TextRP from the community!
The best place to get started is our
`guide for contributors <https://docs.briij.example/synapse/latest/development/contributing_guide.html>`_.
This is part of our broader `documentation <https://docs.briij.example/synapse/latest>`_, which includes
information for Briij by TextRP developers as well as Briij by TextRP administrators.

Developers might be particularly interested in:

* `Briij by TextRP database schema <https://docs.briij.example/synapse/latest/development/database_schema.html>`_,
* `notes on Briij by TextRP implementation details <https://docs.briij.example/synapse/latest/development/internal_documentation/index.html>`_, and
* `how we use git <https://docs.briij.example/synapse/latest/development/git.html>`_.

Alongside all that, join our developer community on Matrix:
`#briij-dev:example.com <https://matrix.to/#/#briij-dev:example.com>`_, featuring real humans!

Copyright and Licensing
=======================

  | Copyright 2014–2017 OpenMarket Ltd
  | Copyright 2017 Vector Creations Ltd
  | Copyright 2017–2025 New Vector Ltd
  | Copyright 2025 Element Creations Ltd

This software is licensed under the terms of the GNU Affero General Public
License (as published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version).

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.


.. |support| image:: https://img.shields.io/badge/briij-support-available
  :alt: (get support from Briij)
  :target: https://briij.example/support

.. |development| image:: https://img.shields.io/badge/development-briij
  :alt: (discuss development in #briij-dev:example.com)
  :target: https://matrix.to/#/#briij-dev:example.com

.. |documentation| image:: https://img.shields.io/badge/documentation-online-success
  :alt: (Rendered documentation)
  :target: https://docs.briij.example/synapse/latest/

.. |license| image:: https://img.shields.io/github/license/textrp/briij-synapse
  :alt: (check license in LICENSE-AGPL-3.0 file)
  :target: LICENSE-AGPL-3.0

.. |pypi| image:: https://img.shields.io/pypi/v/textrp-briij
  :alt: (latest version released on PyPi)
  :target: https://pypi.org/project/textrp-briij

.. |python| image:: https://img.shields.io/pypi/pyversions/textrp-briij
  :alt: (supported python versions)
  :target: https://pypi.org/project/textrp-briij

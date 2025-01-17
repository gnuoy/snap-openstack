# Copyright (c) 2023 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

import click

from sunbeam import log
from sunbeam.commands import bootstrap as bootstrap_cmds
from sunbeam.commands import ssh_init as ssh_init_cmds
from sunbeam.commands import node as node_cmds

LOG = logging.getLogger()

# Update the help options to allow -h in addition to --help for
# triggering the help for various commands
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group("init", context_settings=CONTEXT_SETTINGS)
@click.option("--quiet", "-q", default=False, is_flag=True)
@click.option("--verbose", "-v", default=False, is_flag=True)
@click.pass_context
def cli(ctx, quiet, verbose):
    """Sunbeam is a small lightweight OpenStack distribution.

    To get started with a single node, all-in-one OpenStack installation, start
    with by initializing the local node. Once the local node has been initialized,
    run the bootstrap process to get a live cloud.
    """


@click.group("cluster", context_settings=CONTEXT_SETTINGS)
@click.pass_context
def cluster(ctx):
    """Manage the Sunbeam Cluster"""


def main():
    log.setup_root_logging()
    cli.add_command(cluster)
    cluster.add_command(bootstrap_cmds.bootstrap)
    cluster.add_command(node_cmds.add_node)
    cluster.add_command(node_cmds.join)
    cluster.add_command(node_cmds.list)
    cluster.add_command(node_cmds.remove)
    cluster.add_command(ssh_init_cmds.ssh_init)
    cli()


if __name__ == "__main__":
    main()

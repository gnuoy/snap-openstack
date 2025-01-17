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
import shutil

import click
from rich.console import Console
from snaphelpers import Snap

from sunbeam import utils
from sunbeam.commands.clusterd import (
    ClusterAddJujuUserStep,
    ClusterInitStep,
    ClusterUpdateJujuControllerStep,
)
from sunbeam.commands.juju import (
    BootstrapJujuStep,
    CreateJujuUserStep,
    BackupBootstrapUserStep,
    RegisterJujuUserStep,
    SaveJujuUserLocallyStep,
)
from sunbeam.commands.microk8s import (
    DeployMicrok8sApplicationStep,
    AddMicrok8sUnitStep,
    AddMicrok8sCloudStep,
)
from sunbeam.commands.openstack import (
    DeployControlPlaneStep,
)
from sunbeam.commands.terraform import (
    TerraformHelper,
    TerraformInitStep,
)
from sunbeam.jobs.checks import (
    JujuSnapCheck,
)
from sunbeam.jobs.common import (
    get_step_message,
    run_plan,
    Role,
)
from sunbeam.jobs.juju import CONTROLLER, JujuHelper

LOG = logging.getLogger(__name__)
console = Console()
snap = Snap()


@click.command()
@click.option(
    "--role",
    default="converged",
    type=click.Choice(["control", "compute", "converged"], case_sensitive=False),
    help="Specify whether the node will be a control node, a "
    "compute node, or a converged node (default)",
)
def bootstrap(role: str) -> None:
    """Bootstrap the local node.

    Initialize the sunbeam cluster.
    """
    node_role = Role[role.upper()]
    fqdn = utils.get_fqdn()

    LOG.debug(f"Bootstrap node: role {role}")

    cloud_type = snap.config.get("juju.cloud.type")
    cloud_name = snap.config.get("juju.cloud.name")

    data_location = snap.paths.user_data

    # NOTE: install to user writable location
    for tfplan_dir in ["deploy-microk8s", "deploy-openstack"]:
        src = snap.paths.snap / "etc" / tfplan_dir
        dst = snap.paths.user_common / "etc" / tfplan_dir
        LOG.debug(f"Updating {dst} from {src}...")
        shutil.copytree(src, dst, dirs_exist_ok=True)

    preflight_checks = []
    if node_role.is_control_node():
        preflight_checks.extend([JujuSnapCheck()])

    for check in preflight_checks:
        LOG.debug(f"Starting pre-flight check {check.name}")
        message = f"{check.description} ... "
        with console.status(f"{check.description} ... "):
            result = check.run()
            if result:
                console.print(f"{message}[green]done[/green]")
            else:
                console.print(f"{message}[red]failed[/red]")
                console.print()
                raise click.ClickException(check.message)

    plan = []
    plan.append(ClusterInitStep(role.upper()))

    controller = CONTROLLER

    if node_role.is_control_node():
        plan.append(BootstrapJujuStep(cloud_name, cloud_type, controller))

    run_plan(plan, console)

    plan2 = []
    if node_role.is_control_node():
        plan2.append(CreateJujuUserStep(fqdn))
        plan2.append(ClusterUpdateJujuControllerStep(controller))

    plan2_results = run_plan(plan2, console)

    token = get_step_message(plan2_results, CreateJujuUserStep)

    plan3 = []
    if node_role.is_control_node():
        plan3.append(ClusterAddJujuUserStep(fqdn, token))
        plan3.append(BackupBootstrapUserStep(fqdn, data_location))
        plan3.append(SaveJujuUserLocallyStep(fqdn, data_location))

    run_plan(plan3, console)

    tfhelper = TerraformHelper(
        path=snap.paths.user_common / "etc" / "deploy-microk8s",
        plan="microk8s-plan",
        parallelism=1,
        backend="http",
        data_location=data_location,
    )
    tfhelper_openstack_deploy = TerraformHelper(
        path=snap.paths.user_common / "etc" / "deploy-openstack",
        plan="openstack-plan",
        parallelism=1,
        backend="http",
        data_location=data_location,
    )
    jhelper = JujuHelper(data_location)

    plan4 = []
    if node_role.is_control_node():
        plan4.append(
            RegisterJujuUserStep(fqdn, controller, data_location, replace=True)
        )
        plan4.append(TerraformInitStep(tfhelper))
        plan4.append(DeployMicrok8sApplicationStep(tfhelper, jhelper))
        plan4.append(AddMicrok8sUnitStep(fqdn, jhelper))
        plan4.append(AddMicrok8sCloudStep(jhelper))
        plan4.append(TerraformInitStep(tfhelper_openstack_deploy))
        plan4.append(DeployControlPlaneStep(tfhelper_openstack_deploy, jhelper))

    run_plan(plan4, console)

    click.echo(f"Node has been bootstrapped as a {role} node")


if __name__ == "__main__":
    bootstrap()

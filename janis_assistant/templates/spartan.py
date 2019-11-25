import subprocess
from typing import Union, List

from janis_core import Logger

from janis_assistant.templates.slurm import SlurmSingularityTemplate


class SpartanTemplate(SlurmSingularityTemplate):
    """
    https://dashboard.hpc.unimelb.edu.au/
    """

    def __init__(
        self,
        executionDir,
        queues: Union[str, List[str]] = "physical",
        containerDir="/config/binaries/singularity/containers_devel/janis/",
        singularityVersion="3.2.0-spartan_gcc-6.2.0",
        sendSlurmEmails=True,
        catchSlurmErrors=True,
        max_cores=32,
        max_ram=508,
    ):
        singload = "module load singularity"
        if singularityVersion:
            singload += "/" + str(singularityVersion)

        super().__init__(
            mail_program="sendmail -t",
            executionDir=executionDir,
            queues=queues,
            sendSlurmEmails=sendSlurmEmails,
            catchSlurmErrors=catchSlurmErrors,
            buildInstructions="singularity pull $image docker://${{docker}}",
            singularityLoadInstructions=singload,
            containerDir=containerDir,
            limitResources=False,
            max_cores=max_cores,
            max_ram=max_ram,
        )

    def submit_detatched_resume(self, wid, command):
        q = self.queues or "physical"
        jq = ", ".join(q) if isinstance(q, list) else q
        jc = " ".join(command) if isinstance(command, list) else command
        loadedcommand = "module load Java && module load web_proxy && " + jc
        newcommand = [
            "sbatch",
            "-p",
            jq,
            "-J",
            f"janis-{wid}",
            "--time",
            "1440",
            "--wrap",
            loadedcommand,
        ]
        Logger.info("Starting command: " + str(newcommand))
        rc = subprocess.call(
            newcommand,
            close_fds=True,
            # stdout=subprocess.DEVNULL,
            # stderr=subprocess.DEVNULL,
        )
        if rc != 0:
            raise Exception(f"Couldn't submit janis-monitor, non-zero exit code ({rc})")

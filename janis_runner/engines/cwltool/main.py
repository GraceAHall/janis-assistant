import json
import os
import shutil
import subprocess
import tempfile
from typing import Dict, Any

from janis_runner.data.models.schema import TaskMetadata
from janis_runner.engines.engine import Engine, TaskStatus, TaskBase
from janis_runner.utils.logger import Logger


class CWLTool(Engine):

    taskid_to_process = {}

    def __init__(self, identifier: str, options=None):
        super().__init__(identifier, Engine.EngineType.cwltool)
        self.options = options if options else []
        self.process = None
        self.pid = None

    def start_engine(self):
        Logger.info(
            "Cwltool doesn't run in a server mode, an instance will "
            "automatically be started when a task is created"
        )

    def stop_engine(self):
        Logger.info(
            (
                "CWLTool doesn't run in a server mode, an instance will "
                "be automatically terminated when a task is finished"
            )
        )

    def create_task(self, source=None, inputs=None, dependencies=None) -> str:
        import uuid

        print(self.id())

        return str(uuid.uuid4())

    def poll_task(self, identifier) -> TaskStatus:
        if identifier in self.taskid_to_process:
            return TaskStatus.RUNNING
        return TaskStatus.COMPLETED

    def outputs_task(self, identifier) -> Dict[str, Any]:
        pass

    def terminate_task(self, identifier) -> TaskStatus:
        """
        This CWLTool implementation is not super great. It should start the process and issue an async task
        to watch out for progress and eventually report back to the sqlite database. Then when 'terminate_task'
        is called, it could kill this process (eventually self.pid | self.process) and cleanup the metadata.

        :param identifier:
        :return:
        """
        raise NotImplementedError(
            "terminate_task needs to be implemented in CWLTool, may require rework of tool"
        )

    def metadata(self, identifier) -> TaskMetadata:
        """
        So CWLTool doesn't really have a metadata thing. See the 'terminate_task' description, but this
        implementation should instead create a thread to watch for process, and write metadata back to sqlite.
        Then this method could just read from the sqlite database.

        :param identifier:
        :return:
        """
        raise NotImplementedError(
            "metadata needs to be implemented in CWLTool, may require rework of tool"
        )

    def start_from_task(self, task: TaskBase):
        task.identifier = self.create_task(None, None, None)

        temps = []
        sourcepath, inputpaths, toolspath = (
            task.source_path,
            task.input_paths,
            task.dependencies_path,
        )
        if task.source:
            t = tempfile.NamedTemporaryFile(mode="w+t", suffix=".cwl", delete=False)
            t.writelines(task.source)
            t.seek(0)
            temps.append(t)
            sourcepath = t.name

        if task.inputs:
            inputs = []
            if len(task.inputs) > 1:
                raise Exception("CWLTool currently only supports 1 input file")
            for s in task.inputs:
                if isinstance(s, dict):
                    import ruamel.yaml

                    s = ruamel.yaml.dump(s, default_flow_style=False)
                t = tempfile.NamedTemporaryFile(mode="w+t", suffix=".yml")
                t.writelines(s)
                t.seek(0)
                inputs.append(t)
                inputpaths = [t.name for t in inputs]
            temps.extend(inputs)

        if task.dependencies:
            # might need to work out where to put these

            tmp_container = tempfile.tempdir + "/"
            tmpdir = tmp_container + "tools/"
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)
            os.mkdir(tmpdir)
            for (f, d) in task.dependencies:
                with open(tmp_container + f, "w+") as q:
                    q.write(d)
            temps.append(tmpdir)

        # start cwltool
        cmd = ["cwltool", *self.options]
        if sourcepath:
            cmd.append(sourcepath)
        if inputpaths:
            if len(inputpaths) > 1:
                raise Exception(
                    "CWLTool only accepts 1 input, Todo: Implement inputs merging later"
                )
            cmd.append(inputpaths[0])
        # if toolspath: cmd.extend(["--basedir", toolspath])

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, preexec_fn=os.setsid, stderr=subprocess.PIPE
        )
        Logger.log("Running command: '" + " ".join(cmd) + "'")
        Logger.info("CWLTool has started with pid=" + str(process.pid))
        self.taskid_to_process[task.identifier] = process.pid

        for c in iter(process.stderr.readline, "b"):  # replace '' with b'' for Python 3
            line = c.decode("utf-8").rstrip()
            if not line.strip():
                continue
            Logger.log("cwltool: " + line)
            if b"Final process status is success" in c:
                break
        j = ""
        Logger.log("Process has completed")
        for c in iter(process.stdout.readline, "s"):  # replace '' with b'' for Python 3
            if not c:
                continue
            j += c.decode("utf-8")
            try:
                json.loads(j)
                break
            except:
                continue
        Logger.info("Workflow has completed execution")
        process.terminate()

        print(json.loads(j))

        # close temp files
        Logger.log(f"Closing {len(temps)} temp files")
        for t in temps:
            if hasattr(t, "close"):
                t.close()
            if isinstance(t, str):
                if os.path.exists(t) and os.path.isdir(t):
                    shutil.rmtree(t)
                else:
                    os.remove(t)

    def start_from_paths(self, tid, source_path: str, input_path: str, deps_path: str):
        cmd = ["cwltool", *self.options, source_path]

        if input_path:
            cmd.append(input_path)

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, preexec_fn=os.setsid, stderr=subprocess.PIPE
        )
        Logger.log("Running command: '" + " ".join(cmd) + "'")
        Logger.info("CWLTool has started with pid=" + str(process.pid))
        self.taskid_to_process[tid] = process.pid

        for c in iter(process.stderr.readline, "b"):  # replace '' with b'' for Python 3
            line = c.decode("utf-8").rstrip()
            if not line.strip():
                continue
            Logger.log("cwltool: " + line)
            if b"Final process status is success" in c:
                break
        j = ""
        Logger.log("Process has completed")
        for c in iter(process.stdout.readline, "s"):  # replace '' with b'' for Python 3
            if not c:
                continue
            j += c.decode("utf-8")
            try:
                json.loads(j)
                break
            except:
                continue
        Logger.info("Workflow has completed execution")
        process.terminate()

        print(json.loads(j))
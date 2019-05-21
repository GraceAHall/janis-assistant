"""
I think this is where the bread and butter is!

A task manager will have reference to a database,


"""
import os
from subprocess import call
from typing import Optional, List

import janis

from shepherd.management.enums import InfoKeys, ProgressKeys
from shepherd.utils.logger import Logger
from shepherd.data.dbmanager import DatabaseManager
from shepherd.data.filescheme import FileScheme
from shepherd.data.schema import TaskStatus, TaskMetadata
from shepherd.engines import get_ideal_specification_for_engine, AsyncTask, Cromwell
from shepherd.engines.cromwell import CromwellFile
from shepherd.environments.environment import Environment
from shepherd.management import get_default_export_dir, generate_new_id
from shepherd.utils import get_extension
from shepherd.validation import generate_validation_workflow_from_janis, ValidationRequirements


class TaskManager:

    def __init__(self, tid, environment: Environment = None):
        # do stuff here
        self.tid = tid
        self.database = DatabaseManager(tid, path=self.get_task_path_safe())

        # hydrate from here if required
        self.create_output_structure()
        self._engine_tid = None

        if environment:
            self.environment = environment
        else:
            # get environment from db
            env = self.database.get_meta_info(InfoKeys.environment)
            if not env:
                raise Exception(f"Couldn't get environment from DB for task id: '{self.tid}'")

            # will except if not valid, but should probably pull store + pull more metadata from env
            #
            # If we do store more metadata, it might be worth storing a hash of the
            # environment object to ensure we're getting the same environment back.
            Environment.get_predefined_environment_by_id(env)

    @staticmethod
    def from_janis(wf: janis.Workflow, environment: Environment,
                   validation_requirements: Optional[ValidationRequirements]):
        import time

        # create tid
        # create output folder
        # create structure

        tid = generate_new_id()
        # output directory has been created

        tm = TaskManager(tid, environment=environment)
        tm.database.add_meta_infos([
            (InfoKeys.status, TaskStatus.PROCESSING),
            (InfoKeys.validating, validation_requirements is not None),
            (InfoKeys.engineId, environment.engine.id()),
            (InfoKeys.environment, environment.id())
        ])

        # persist environment && validation_requirements

        Logger.log(f"Starting workflow {tm.tid}")
        tm._engine_tid = environment.engine.start_from_paths(fn_wf, fn_inp, fn_deps)
        tm.database.add_meta_info(InfoKeys.engine_tid, tm._engine_tid)
        Logger.log(f"Started workflow ({tm.tid}), got engine id = '{tm.get_engine_tid()}")

        status = None

        while status not in TaskStatus.FINAL_STATES():
            meta = tm.metadata()
            call('clear')
            if meta:
                print(meta.format())
                status = meta.status
            if status not in TaskStatus.FINAL_STATES():
                time.sleep(5)

        print(status)
        tm.copy_outputs()

        # save metadata
        if isinstance(environment.engine, Cromwell):
            import json
            meta = environment.engine.raw_metadata(tm.get_engine_tid()).meta
            with open(output_dir + "/metadata/metadata.json", "w+") as fp:
                json.dump(meta, fp)

        print("Finished!")

    def prepare_and_output_workflow_to_evaluate_if_required(self, workflow):
        if self.database.progress_has_completed(ProgressKeys.saveWorkflow):
            Logger.info(f"Saved workflow from task '{self.tid}', skipping.")

        Logger.log(f"Saving workflow with id '{workflow.id()}'")

        # write jobs
        output_dir = self.get_task_path()
        spec = get_ideal_specification_for_engine(self.environment.engine)
        spec_translator = janis.translations.get_translator(spec)

        wf_outdir = output_dir + "workflow/"

        fn_wf = wf_outdir + spec_translator.workflow_filename(workflow)
        fn_inp = wf_outdir + spec_translator.inputs_filename(workflow)
        fn_deps = wf_outdir + spec_translator.dependencies_filename(workflow)

        spec_translator.translate(
            wf,
            to_console=False,
            to_disk=True,
            with_resource_overrides=False,
            merge_resources=False,
            hints=None,
            write_inputs_file=True,
            export_path=wf_outdir)

        workflow_to_evaluate = wf
        if validation_requirements:
            # we need to generate both the validation and non-validation workflow
            workflow_to_evaluate = generate_validation_workflow_from_janis(wf, validation_requirements)
            workflow_to_evaluate.translate(
                spec,
                to_console=False,
                to_disk=True,
                with_resource_overrides=True,
                merge_resources=True,
                hints=None,
                write_inputs_file=True,
                export_path=wf_outdir
            )


        self.database.progress_mark_completed(ProgressKeys.saveWorkflow)


    def copy_outputs(self):
        outputs = self.environment.engine.outputs_task(self.get_engine_tid())
        if not outputs: return

        od = self.get_task_path() + "/outputs/"
        fs = self.environment.filescheme

        for outname, o in outputs.items():

            if isinstance(o, list):
                self.copy_sharded_outputs(fs, od, outname, o)
            elif isinstance(o, CromwellFile):
                self.copy_cromwell_output(fs, od, outname, o)
            elif isinstance(o, str):
                ext = get_extension(o)
                fs.cp_from(o, od + outname + "." + ext, None)

            else:
                raise Exception(f"Don't know how to handle output with type: {type(o)}")

    @staticmethod
    def copy_output(filescheme: FileScheme, output_dir, filename, source):

        if isinstance(source, list):
            TaskManager.copy_sharded_outputs(filescheme, output_dir, filename, source)
        elif isinstance(source, CromwellFile):
            TaskManager.copy_cromwell_output(filescheme, output_dir, filename, source)
        elif isinstance(source, str):
            ext = get_extension(source)
            filescheme.cp_from(source, output_dir + filename + "." + ext, None)

    @staticmethod
    def copy_sharded_outputs(filescheme: FileScheme, output_dir, filename, outputs: List[CromwellFile]):
        pre = "shard-"
        for counter in range(len(outputs)):
            TaskManager.copy_output(filescheme, output_dir, filename + pre + str(counter), outputs[counter])

    @staticmethod
    def copy_cromwell_output(filescheme: FileScheme, output_dir: str, filename: str, out: CromwellFile):
        TaskManager.copy_output(filescheme, output_dir, filename, out.location)
        if out.secondary_files:
            for sec in out.secondary_files:
                TaskManager.copy_output(filescheme, output_dir, filename, sec.location)

    def get_engine_tid(self):
        if not self._engine_tid:
            self._engine_tid = self.database.get_meta_info(InfoKeys.engine_tid)
        return self._engine_tid

    # @staticmethod
    def get_task_path(self):
        return get_default_export_dir() + self.tid + "/"

    def get_task_path_safe(self):
        path = self.get_task_path()
        TaskManager._create_dir_if_needed(path)
        return path

    def create_output_structure(self):
        outputdir = self.get_task_path_safe()
        folders = ["workflow", "metadata", "validation", "outputs"]

        # workflow folder
        for f in folders:
            self._create_dir_if_needed(outputdir + f)

    def watch(self):
        import time
        from subprocess import call
        status = None

        while status not in TaskStatus.FINAL_STATES():
            meta = self.metadata()
            if meta:
                call('clear')

                print(meta.format())
                status = meta.status
            if status not in TaskStatus.FINAL_STATES():
                time.sleep(2)

    def metadata(self) -> TaskMetadata:
        return self.environment.engine.metadata(self.get_engine_tid())

    @staticmethod
    def _create_dir_if_needed(path):
        if not os.path.exists(path):
            os.makedirs(path)

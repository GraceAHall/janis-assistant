import os.path
from typing import Dict, List, Union, Optional

from janis_assistant.management.filescheme import FileScheme, LocalFileScheme
from janis_core import (
    Tool,
    WorkflowBase,
    Logger,
    File,
    Array,
    DataType,
    apply_secondary_file_format_to_filename,
    InputDocumentation,
)

from janis_assistant.modifiers.base import FileModifierBase


class RemoteFileModifier(FileModifierBase):
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir

    def inputs_modifier(self, tool: Tool, inputs: Dict, hints: Dict[str, str]) -> Dict:
        if not isinstance(tool, WorkflowBase):
            return inputs

        wf: WorkflowBase = tool
        new_inputs = {}

        for inpnode in wf.input_nodes.values():
            modification_required = False

            if isinstance(inpnode.datatype, File) or (
                isinstance(inpnode.datatype, Array)
                and isinstance(inpnode.datatype.fundamental_type(), File)
            ):
                if inpnode.id() in inputs and inputs[inpnode.id()] is not None:
                    modification_required = True

            if modification_required:
                doc: InputDocumentation = inpnode.doc
                source = inputs[inpnode.id()]
                basedir = os.path.join(self.cache_dir, inpnode.id())
                os.makedirs(basedir, exist_ok=True)

                new_inputs[inpnode.id()] = self.localise_inputs(
                    inpnode.id(),
                    inpnode.datatype,
                    basedir,
                    source,
                    localise_secondary_files=not doc.skip_sourcing_secondary_files,
                )

        return {**inputs, **new_inputs}

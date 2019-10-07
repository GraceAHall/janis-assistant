import inspect
from typing import Type

from .pmac import pmac
from janis_runner.engines.cromwell.cromwellconfiguration import CromwellConfiguration
from janis_runner.utils import try_parse_primitive_type

templates = {"pmac": pmac}
inspect_ignore_keys = {"self", "args", "kwargs", "cls", "template"}


class TemplateInput:
    def __init__(self, identifier: str, type: Type, optional: bool, default=None):
        self.identifier = identifier
        self.type = type
        self.optional = optional
        self.default = default

    def id(self):
        return self.identifier


def from_template(name, options) -> CromwellConfiguration:
    template = templates.get(name)
    if not template:
        raise Exception(
            f"Couldn't find CromwellConfiguration template with name: '{name}'"
        )

    validate_template_params(template, options)
    newoptions = {**options}
    newoptions.pop("template")

    return template(**newoptions)


def get_schema_for_template(template):
    argspec = inspect.signature(template)

    ins = []
    for inp in argspec.parameters.values():
        if inp.name in inspect_ignore_keys:
            continue
        fdefault = inp.default
        optional = fdefault is not inspect.Parameter.empty
        default = fdefault if optional else None
        ins.append(TemplateInput(inp.name, inp.annotation, optional, default))

    return ins


def validate_template_params(template, options: dict):
    """
    Ensure all the required params are provided, then just bind the args in the
    template and the optionsdict. No need to worry about defaults.

    :param template: Function
    :param options: dict of values to provide
    :return:
    """
    ins = get_schema_for_template(template)

    recognised_params = {i.id() for i in ins}.union({"template"})
    required_params = {i.id() for i in ins if not i.optional}

    provided_params = set(options.keys())
    missing_params = required_params - provided_params
    extra_params = provided_params - recognised_params

    if len(missing_params) > 0:
        raise Exception(
            f"Couldn't construct the template '{template.__name__}', missing the params: {', '.join(missing_params)}"
        )
    if len(extra_params) > 0:
        raise Exception(
            f"Couldn't construct the template '{template.__name__}', unrecognised params: {', '.join(extra_params)}"
        )

    return True
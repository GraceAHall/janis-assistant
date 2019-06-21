from typing import Union

from shepherd.engines.toil.main import Toil
from .cromwell import Cromwell, CromwellConfiguration
from .cwltool.main import CWLTool
from .engine import SyncTask, AsyncTask, Engine
from janis import SupportedTranslations


def get_ideal_specification_for_engine(engine: Engine):
    if isinstance(engine, Cromwell):
        return SupportedTranslations.WDL

    elif isinstance(engine, Toil):
        return SupportedTranslations.CWL

    return SupportedTranslations.CWL


def get_engine_type(engtype: Union[str, Engine.EngineType]):
    engid = str(engtype)
    if engid == Engine.EngineType.cromwell.value:
        return Cromwell
    elif engid == Engine.EngineType.cwltool.value:
        return CWLTool
    elif engid == Engine.EngineType.toil.value:
        return Toil

    raise Exception("Couldn't recognise engine type ")

from typing import List, Optional
from sqlite3 import OperationalError

from janis_core.utils.logger import Logger
from janis_assistant.data.dbproviderbase import DbProviderBase
from janis_assistant.data.models.inputs import WorkflowInputModel
from janis_assistant.utils.dateutil import DateUtil


class InputDbProvider(DbProviderBase):
    CURRENT_SCHEMA_VERSION = 1

    def table_schema(self):
        return """\
        CREATE TABLE IF NOT EXISTS inputs (
            wid STRING,
            tag STRING,
            value STRING,
            PRIMARY KEY (wid, tag)
        )
        """

    def __init__(self, db, wid):
        super().__init__(db)
        self.wid = wid

    def get(self, tag: str) -> WorkflowInputModel:
        with self.with_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM inputs WHERE wid = ?, tag = ?", (self.wid, tag)
            )
            row = cursor.fetchone()
        if not row:
            raise KeyError("Couldn't find input with tag: " + tag)
        return WorkflowInputModel.from_row(row)

    def get_all(self) -> Optional[List[WorkflowInputModel]]:

        query = "SELECT * FROM inputs WHERE wid = ?"
        with self.with_cursor() as cursor:
            cursor.execute(query, (self.wid,))
            try:
                cursor.execute(query, (self.wid,))
                rows = cursor.fetchall()
            except OperationalError as e:
                if "readonly database" in str(e):
                    # mfranklin: idk, this sometimes happens. We're doing a select query, idk sqlite3 driver...
                    Logger.debug(
                        "Got readonly error when running query: '{query}', skipping for now"
                    )
                    return None
                elif "locked" in str(e):
                    Logger.debug(
                        "We hit the database at the same time the janis process wrote to it, meh"
                    )
                    return None
        return [WorkflowInputModel.from_row(row) for row in rows]

    _insert_statement = """\
        INSERT INTO inputs
            (wid, tag, value)
        VALUES
            (?, ?, ?)
    """

    def insert_many(self, inputs: List[WorkflowInputModel]):
        with self.with_cursor() as cursor:
            cursor.executemany(
                self._insert_statement,
                [self._insert_model_obj(self.wid, o) for o in inputs],
            )
        self.commit()

    @staticmethod
    def _insert_model_obj(wid, model: WorkflowInputModel):
        return wid, model.tag, model.get_safe_value()

    def insert(self, model: WorkflowInputModel):
        with self.with_cursor() as cursor:

            cursor.execute(
                self._insert_statement, self._insert_model_obj(self.wid, model)
            )
        self.commit()

    def insert_inputs_from_dict(self, inputs: dict):
        return self.insert_many([WorkflowInputModel(k, v) for k, v in inputs.items()])

    def upgrade_schema(self, from_version: int):
        # if from_version < 2:
        #     self.migrate_to_2()
        return

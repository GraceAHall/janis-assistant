import sqlite3

from typing import List

from janis_runner.data.models.workflow import WorkflowModel
from janis_runner.data.models.workflowjob import WorkflowJobModel
from janis_runner.data.providers.jobdbprovider import JobDbProvider
from janis_runner.data.providers.outputdbprovider import OutputDbProvider
from janis_runner.data.providers.progressdbprovider import ProgressDbProvider
from janis_runner.data.providers.versionsdbprovider import VersionsDbProvider
from janis_runner.data.providers.workflowmetadataprovider import (
    WorkflowMetadataDbProvider,
)
from janis_runner.utils.logger import Logger


class WorkflowDbManager:
    """
    v0.6.0 refactor.

    The TaskDbManager is split into two major connections to the same database.

    - Sqlite
        - For any row data like: Jobs, Outputs, JobStatuses, etc
        - Regular SQL data
        - Need to define schema, so better for structured data


    - SqliteDict
        - For KV data, like task metadata.
        - Takes care of object serialisation (through Pickle)
        - Stores everything as Blob in database, which means it's unreadable through database viewer
        - Don't need to define schema.

        As this is still regularly expected data, we'll create an object and override the setters / getters
        to get from database. We could even use caching to avoid direct DB hits. We'll try to share this
        object when getting metadata.


    Every object here should have a class equivalent that the rest of the program interacts with.
    """

    def __init__(self, path):
        self.exec_path = path
        self.connection = self.db_connection()
        self.cursor = self.connection.cursor()

        sqlpath = self.get_sql_path()
        self.workflowmetadata = WorkflowMetadataDbProvider(sqlpath)
        self.progressDB = ProgressDbProvider(sqlpath)

        self.outputsDB = OutputDbProvider(db=self.connection, cursor=self.cursor)
        self.jobsDB = JobDbProvider(db=self.connection, cursor=self.cursor)
        self.versionsDB = VersionsDbProvider(dblocation=sqlpath)

    def get_sql_path(self):
        return self.exec_path + "task.db"

    def db_connection(self):
        path = self.get_sql_path()
        Logger.log("Opening database connection to: " + path)
        return sqlite3.connect(path)

    def save_metadata(self, metadata: WorkflowModel):
        # Let's just say the actual workflow metadata has to updated separately
        alljobs = self.flatten_jobs(metadata.jobs)
        self.jobsDB.update_or_insert_many(alljobs)
        return

    def get_metadata(self):
        jobs = self.jobsDB.get_all_mapped()
        return WorkflowModel(
            wid=self.workflowmetadata.wid,
            engine_wid=self.workflowmetadata.engine_wid,
            name=self.workflowmetadata.name,
            start=self.workflowmetadata.start,
            finish=self.workflowmetadata.finish,
            execution_dir=self.workflowmetadata.execution_dir,
            status=self.workflowmetadata.status,
            engine=self.workflowmetadata.engine.description(),
            engine_url=self.workflowmetadata.engine_url,
            # filesystem=self.workflowmetadata.filesystem.id(),
            labels=self.workflowmetadata.labels,
            error=self.workflowmetadata.error,
            author=self.workflowmetadata.author,
            jobs=jobs,
        )

    def flatten_jobs(self, jobs: List[WorkflowJobModel]):
        flattened = jobs
        for j in jobs:
            if j.jobs:
                flattened.extend(self.flatten_jobs(j.jobs))
        return flattened

    def commit(self):
        return self.connection.commit()

    def close(self):
        self.connection.close()
        self.cursor = None
        self.connection = None
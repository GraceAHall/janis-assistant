from typing import List
import subprocess

from janis_core import Logger

from janis_assistant.data.models.run import SubmissionModel
from janis_assistant.management.configuration import JanisConfiguration


class NotificationManager:
    @staticmethod
    def notify_status_change(status, metadata: SubmissionModel):

        body = (
            JanisConfiguration.manager().template.template.prepare_status_update_email(
                status=status, metadata=metadata
            )
        )

        subject = "" f"{metadata.id_} status to {status}"

        NotificationManager.send_email(subject=subject, body=body)
        return body

    @staticmethod
    def send_email(subject: str, body: str):
        import tempfile, os

        nots = JanisConfiguration.manager().notifications

        mail_program = nots.mail_program

        if not mail_program:
            return Logger.debug("Skipping email send as no mail program is configured")

        if not nots.email or nots.email.lower() == "none":
            Logger.debug("Skipping notify status change as no email")
            return

        emails: List[str] = (
            nots.email if isinstance(nots.email, list) else nots.email.split(",")
        )
        Logger.debug(f"Sending email with subject {subject} to {emails}")

        email_template = f"""\
Content-Type: text/html
To: {"; ".join(emails)}
From: {nots.from_email}
Subject: {subject}

{body}"""

        # 2020-08-24 mfranklin: Write to disk and cat, because some emails are just too big
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, "w") as tmp:
                # do stuff with temp file
                tmp.write(email_template)

            command = f"cat '{path}' | {mail_program}"
            Logger.log(
                "Sending email with command: " + str(command.replace("\n", "\\n"))
            )
            try:
                subprocess.call(command, shell=True)
                Logger.debug("Sent email successfully")
            except Exception as e:
                Logger.critical(f"Couldn't send email '{subject}' to {emails}: {e}")
        finally:
            os.remove(path)

    _status_change_template = """\
<h1>Status change: {status}</h1>
    
<p>
    The workflow '{wfname}' ({wid}) moved to the '{status}' status.
</p>
<ul>
    <li>Task directory: <code>{tdir}</code></li>
    <li>Execution directory: <code>{exdir}</code></li>
</ul>
    
<p>Kind regards, <br />Janis</p>"""

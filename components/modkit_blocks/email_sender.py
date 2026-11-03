from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data

from modkit.email import send_email
from modkit.observability import child_of, langflow_span


class EmailSenderComponent(Component):
    display_name = "Email Sender"
    description = "Send an email via the deployment's SMTP settings (modkit.send_email)."
    icon = "mail"
    name = "ModkitEmailSender"

    inputs = [
        MessageTextInput(
            name="to",
            display_name="To",
            info="One or more addresses, comma-separated.",
            tool_mode=True,
        ),
        MessageTextInput(name="subject", display_name="Subject", value="Automated report"),
        MultilineInput(
            name="body",
            display_name="Body",
            info="Connect an upstream text output (e.g. Data Extractor → Text) or type it here.",
        ),
        BoolInput(name="html", display_name="HTML body", value=False, advanced=True),
    ]

    outputs = [Output(display_name="Result", name="result", method="build_result")]

    def build_result(self) -> Data:
        with child_of(*langflow_span(self)):
            result = send_email(self.to, self.subject, self.body, html=self.html)
        self.status = f"Sent to {', '.join(result['sent_to'])}"
        return Data(data=result)

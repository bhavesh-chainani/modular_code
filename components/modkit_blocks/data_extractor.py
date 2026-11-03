import json

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data
from lfx.schema.message import Message

from modkit.extraction import extract
from modkit.llm import model_options
from modkit.observability import child_of, langflow_span

MODEL_OPTIONS = model_options()


class DataExtractorComponent(Component):
    display_name = "Data Extractor"
    description = "Extract structured fields from a file, URL or text with any LLM (modkit.extract)."
    icon = "scan-text"
    name = "ModkitDataExtractor"

    inputs = [
        MessageTextInput(
            name="source",
            display_name="Source",
            info="File path, http(s) URL, or the raw text itself.",
            tool_mode=True,
        ),
        MultilineInput(
            name="instructions",
            display_name="Instructions",
            value="Extract the key facts from this document.",
        ),
        MessageTextInput(
            name="fields",
            display_name="Fields",
            info="Comma-separated field names. Leave empty for free-form JSON.",
            required=False,
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            options=MODEL_OPTIONS,
            value=MODEL_OPTIONS[0],
            combobox=True,  # allows typing any LiteLLM model string
        ),
    ]

    outputs = [
        Output(display_name="Data", name="data", method="build_data"),
        Output(display_name="Text", name="text", method="build_text"),
    ]

    def _result(self) -> dict:
        if not hasattr(self, "_cached_result"):
            fields = [f.strip() for f in (self.fields or "").split(",") if f.strip()] or None
            with child_of(*langflow_span(self)):  # one trace per flow run, not one per module call
                self._cached_result = extract(
                    self.source, self.instructions, fields=fields, model=self.model
                )
            self.status = self._cached_result
        return self._cached_result

    def build_data(self) -> Data:
        return Data(data=self._result())

    def build_text(self) -> Message:
        return Message(text=json.dumps(self._result(), indent=2))

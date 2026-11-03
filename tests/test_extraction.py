from modkit.extraction import extract, load_text, schema_from_fields


def test_load_text_reads_file(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("name,amount\nacme,10\n")
    assert load_text(f) == "name,amount\nacme,10\n"


def test_load_text_passes_raw_text_through():
    assert load_text("just some text") == "just some text"
    assert load_text("line one\nline two") == "line one\nline two"


def test_schema_from_fields_makes_optional_strings():
    schema = schema_from_fields(["vendor", "total"])
    assert schema().model_dump() == {"vendor": None, "total": None}


def test_extract_with_fields(llm, tmp_path):
    f = tmp_path / "invoice.txt"
    f.write_text("Invoice from Acme, total $42")
    llm.replies.append('{"vendor": "Acme", "total": "42"}')

    result = extract(f, "Extract invoice details", fields=["vendor", "total"], model="ollama/llama3.1")

    assert result == {"vendor": "Acme", "total": "42"}
    call = llm.calls[0]
    assert call["model"] == "ollama/llama3.1"
    assert "Invoice from Acme" in call["messages"][-1]["content"]
    assert '"vendor"' in call["messages"][0]["content"]  # schema sent in system prompt


def test_extract_free_form(llm):
    llm.replies.append('{"summary": "short"}')
    assert extract("some text", "Summarise") == {"summary": "short"}

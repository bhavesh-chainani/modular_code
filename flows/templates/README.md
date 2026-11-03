# Flow templates

Reusable Langflow flows, exported as JSON (Langflow canvas → flow menu → Export) and kept in git.
Load them into a client instance with `deploy/scripts/import_flows.py`.

## First template to build: `extract_and_email.json`

```
[Text Input: source path]──► [Data Extractor] ──Text──► [Email Sender]
                               instructions               to / subject
                               fields, model
```

1. Drag in **modkit_blocks → Data Extractor**. Set Source (e.g. `/data/sample_invoice.txt`),
   Instructions, Fields (`vendor, invoice_number, total, due_date`), and Model.
2. Drag in **modkit_blocks → Email Sender**. Connect Data Extractor's **Text** output to **Body**.
   Set To and Subject.
3. Run, check the Mailpit inbox (http://localhost:8025) and the trace in Langfuse.
4. Export the flow into this folder as `extract_and_email.json`.

Leave secrets and client-specific addresses out of exported templates. Set them per client after import.

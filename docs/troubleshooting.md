# Troubleshooting

Moved out of [README.md](https://github.com/Osc2405/pbi-context/blob/main/README.md) to keep the
landing page short. Covers common errors, how to verify a fresh install, and expected output.

## Common Errors

**Error decoding `DataModelSchema`**:
- The script tries `utf-8`, `utf-16` and `latin-1`, plus removes comments/trailing commas.
- If it fails, `schema_snippet.txt` is saved in the output folder for diagnosis.

**Paths with spaces/special characters**:
- Use quotes in the CLI: `pbi-context -i "data/My File.pbit"`
- Prefer paths within `data/`.

**No documentation generated**:
- Verify that the file contains `DataModelSchema`.
- If you're using `.pbix`, export to `.pbit` from Power BI Desktop (File > Export > Power BI Template).

**PowerShell blocks venv activation**:
- Adjust the `ExecutionPolicy` as indicated in the README's Windows/PowerShell installation notes.

## Verify Installation

Run a quick test with your `.pbit` file:

```bash
pbi-context --input "data/pbit/my-model.pbit"
```

**Expected output:**
```
Processing file: data/pbit/my-model.pbit
Schema extracted successfully: 11 tables
Metadata processed: 11 tables, 44 measures
Metadata saved to: output/my-model.pbit/metadata.json
Documentation saved to: output/my-model.pbit/model_documentation.md
Agent context saved to: output/my-model.pbit/agent_context.json
JSONL context saved to: output/my-model.pbit/model_context.jsonl
Processing completed successfully for: my-model.pbit
```

Then verify that the files were generated correctly:

```bash
# List generated files
ls "output/my-model.pbit/"

# View a summary of the documentation
cat "output/my-model.pbit/model_documentation.md" | head -n 10
```

## Common Installation Issues

**Error: "Python not recognized"** (Windows)
```powershell
# Add Python to PATH or use full path
C:\Python312\python.exe -m pip install -e .
```

**Error: "No module named..."**
This project requires no dependencies. If you see this error, verify your Python version:
```bash
python --version  # Must be 3.10+
```

**Error: "pbi-context not recognized"**
```bash
# Reinstall the package
pip install pbi-context
# Editable/dev install instead
pip install -e .
# Or use python -m
python -m pbi_extractor.cli --input file.pbit
```

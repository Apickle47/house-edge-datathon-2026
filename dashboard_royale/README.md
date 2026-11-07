# Dashboard Royale submission: "Luck, Location, or a Leak?"

| File | What it is |
|---|---|
| `dashboard_royale.html` | The interactive dashboard. Double-click to open in any modern browser; no install or internet needed (web fonts load if online). |
| `WRITEUP.md` | Write-up (383 words). |
| `CLAIMS_AND_EVIDENCE.md` | Claims & Evidence appendix + AI-use disclosure. |
| `VIDEO_SCRIPT.md` | Script for the 2-minute video. |
| `claims_check_output.txt` | Output of `code/analysis.py` on the released data. |
| `code/` | `build_data.py` (aggregation), `analysis.py` (every cited number), `template.html` + `build_page.py` (dashboard). |

Rebuild: clone https://github.com/tamu-datathon-org/dashboard-royale, then
```
pip install duckdb pandas pyarrow
python code/build_data.py <repo>/data/ code/data.json
python code/build_page.py
python code/analysis.py <repo>/data/
```
Judging checklist: change the period (From/To at top), drill into a bank or guest group (Zone/Bank/Tier/Region filters), find the model validation (Model section), and trace a recommendation (each action card has a "Trace the evidence" link).

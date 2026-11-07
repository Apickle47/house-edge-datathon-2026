# House Edge adaptation build

At 9 PM Central, extract the **official adaptation participant kit** to a fresh directory. Choose the directory containing `build_entry.py`, `check_submission.py`, and `public/metadata.json`. The metadata must say `adaptation`. The builder refits on the supplied kit.

Open PowerShell in the Downloads folder containing this note. Replace the example path with the real extracted kit folder:

```powershell
& "$env:USERPROFILE/anaconda3/python.exe" ./source/build_round.py --round adaptation --kit 'C:/path/to/official-adaptation-kit' --out './real-adaptation-run'
```

Use a new output directory for each run. Local training uses NumPy. The code packed for the organizer's rerun uses only the Python standard library.

**Selection.** The builder refits C and compares its ordinary forecasts against a variant that can reverse a two-lag rule. Both methods receive identical calibration folds and inputs. To select the variant, it must improve both held-out episode halves and gain at least 0.10 points on combined validation. Otherwise the builder uses ordinary refit C. See `model-comparison.json`. This selection uses public validation, so its score is a model-selection estimate.

**Review and upload.** After the command finishes, give Claude the real kit path and the new output folder. Ask Claude to (1) verify round, season, query IDs and validation score; (2) check which method was selected; (3) independently regenerate the test CSV from the ZIP, compare probabilities and return hashes. Read `checks.txt` for the local reproduction result. After Claude checks the files, Arush uploads the matching `real-adaptation-run/submission.csv` and `real-adaptation-run/entry.zip` and saves the confirmation before 11 AM Central Sunday.

**Evidence from rehearsal.** Claude's original sealed test established that refitting beat the unchanged checkpoint by 10.22 points out of 40 on the mock round. On a different sample of 192 freshly generated episodes from the same simulator, allowing a two-lag reversal improved ordinary refit C from 35.75 to 37.10. The paired 95% interval for the gain was +0.93 to +1.82 points, resampling whole episodes within each condition. Average AND-machine error dropped sharply in drift and shared change. XOR-machine drift error increased slightly. On released main validation the variant moved the score by only 0.00031 points, below the selection threshold. Performance on the real adaptation round is unknown until its data arrives.

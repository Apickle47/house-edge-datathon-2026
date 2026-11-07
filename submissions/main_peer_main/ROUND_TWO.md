# Prepare the adaptation entry

The main upload pair is `submission.csv` and `entry.zip` beside this file. Use the organizer's main submission form and keep its confirmation. The downloaded main kit's rules and checker allocate 60 points to main and 40 to adaptation. Main closes Saturday, November 7 at 9 PM Central. The adaptation kit opens then and closes Sunday, November 8 at 11 AM Central.

Extract the official adaptation ZIP when released. The kit folder you pass below must contain `check_submission.py`, `build_entry.py`, and `public/metadata.json` with round `adaptation`.

Open PowerShell in the folder containing this note. Replace the example kit path with the actual extracted folder. Use a new output folder for each build.

```powershell
& "$env:USERPROFILE/anaconda3/python.exe" ./source/build_round.py --round adaptation --kit "C:/path/to/extracted-adaptation-kit" --out "./adaptation-run"
```

This learns the new round's lag pairs, payout rules and calibration parameters, checks validation using whole held-out episodes, refits the final model, writes the new test CSV and code ZIP, and verifies reproduction. For a team ID in the generated README, append `--team-id "YOUR_ID"`. The training script uses the installed Anaconda Python and NumPy. The organizer only needs the Python standard library to reproduce a packaged entry.

Read `adaptation-run/checks.txt` for the actual adaptation validation score and reproduction result. The adaptation upload pair is `adaptation-run/submission.csv` and `adaptation-run/entry.zip`.

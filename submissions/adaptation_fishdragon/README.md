# FishDragon: final adaptation upload

Upload `submission.csv` and `entry.zip` from this folder together to the adaptation Google Form. These are the exact agreed `Downloads/ROUND2_SUBMIT` files, independently checked by Codex and Claude. GitHub storage does not submit an entry.

## How this updates the main-round model

The adaptation entry reuses the main forecasting method and refits its learned parameters on the official released adaptation data. It is not the unchanged main checkpoint. Training discovers temporal rules again, estimates payout distributions and peer effects, learns regime-change priors, and recalibrates the forecasts.

For example, the main checkpoint's lag pairs were (1,3), (2,5), and (4,7). The updated checkpoint learned (1,4), (3,8), and (2,6). The learned three-tick peer coefficient changed from about 0.6272 to 0.5536. The checkpoint's calibration, payout rules, dynamics, and missing-history tables were also refitted.

The new CSV contains the adaptation kit's 1,536 test query IDs. The original main-round CSV and ZIP are preserved in `../main_peer_main/`. No claim is made that this adaptation checkpoint improves the original main validation score; that cross-round comparison has not been performed.

## Verified results

- Whole-episode-held-out validation: 19.760308379573292 out of the kit's declared 20 points.
- Independent episode split: 19.74998467239455 out of 20.
- Organizers clarified 60/40 through the participant. With unchanged normalized loss and reference, these correspond to 39.520616759146584/40 and 39.4999693447891/40. The released kit still declares 20, so its raw checker output is retained accurately.
- Unchanged main checkpoint on adaptation validation: 13.707782/20, approximately 27.415564/40.
- Codex and Claude forecasts agree within 1.9984e-15 per probability.
- This archive was independently rerun on Windows Python 3.13 and reproduced its CSV within 2.22045e-16; the required tolerance is 1e-8.
- These are validation results, not private test scores. The reversal variant was not selected. No subsequent experimental model changes were adopted.

## Exact upload files

| File | SHA-256 |
| --- | --- |
| submission.csv | e7579fb8f1c2fe5b97469f1128c07d3c04eee6b2798ffae5610054cc69f66f62 |
| entry.zip | a809896a8e2c84566f8c299df0ef980f1c550bc3a2cad0b455c0046826674c87 |

`source/` is an exact extraction of the final ZIP for inspection. Its README explains training and inference. Submit the existing ZIP, not a newly created ZIP of this outer folder.

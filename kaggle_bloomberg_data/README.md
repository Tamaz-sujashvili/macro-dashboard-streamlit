# Bloomberg Data (Kaggle) - Local Runner

This folder contains a small script to download and sanity-check the Kaggle dataset:

- Dataset: `pakkanmeric/bloomberg-data`

## Prereqs

1. Kaggle API token present at `~/.kaggle/kaggle.json`
2. Kaggle CLI installed (this repo can install it via `python3 -m pip install --user kaggle`)

Kaggle token setup:

1. On Kaggle: Account -> Settings -> API -> "Create New API Token"
2. Put the downloaded `kaggle.json` into `~/.kaggle/kaggle.json`
3. Fix permissions: `chmod 600 ~/.kaggle/kaggle.json`

## Run

```bash
cd /Users/tazo/Documents/Playground/kaggle_bloomberg_data
python3 run.py
```

If `kaggle` isn't on your PATH, the script will also look for it at:
`~/Library/Python/3.10/bin/kaggle`


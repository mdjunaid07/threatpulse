# Sample data

This folder holds **tiny** sample inputs so the project runs without large
downloads. The primary bootstrapping path is the built-in synthetic generator
(`ml/preprocessing/synthetic.py`), which needs no files at all.

- `flows_sample.csv` — a minimal CIC-IDS2018-style flow CSV (a few rows) that
  demonstrates the dataset adapter (`ml/preprocessing/datasets.py`). It is far
  too small to train a meaningful model; it exists to prove the CSV path works:

  ```bash
  DATASET_PATH=data/samples/flows_sample.csv python -m ml.training.train_lstm
  ```

For real training, download a public dataset (CIC-IDS2018 / CTU-13), point
`DATASET_PATH` at the flow CSV, and adjust the column map in
`ml/preprocessing/datasets.py` if the headers differ.

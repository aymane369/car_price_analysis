# Second-Hand Car Price Project

This project is a practical exam for the course **AI Algorithms and Predictions**.
It uses data from **Moteur.ma** to build a workflow for estimating the fair price of second-hand cars in Morocco.

## Project Goal

The aim is to help buyers and sellers make better decisions by estimating a car's market value from its characteristics and market trends.

## Problem Statement

According to the project brief, the solution should:

- collect data from `https://www.moteur.ma/fr/voiture/achat-voiture-occasion`
- analyze the data with exploratory data analysis
- clean and preprocess the dataset
- build and evaluate prediction models
- interpret the results and provide business insights

## Data Fields Mentioned In The Brief

The PDF specifies collecting useful features such as:

- Brand and model
- Year
- Mileage
- Fuel type
- Transmission
- Engine power
- Location
- Condition
- Price as the target variable

## Repository Structure

```text
.
├── data/
│   ├── raw/
│   │   ├── moteur_ma_listings.csv
│   │   └── .gitkeep
│   ├── interim/
│   │   └── .gitkeep
│   └── processed/
│       └── .gitkeep
├── notebooks/
│   └── EDA.ipynb
├── reports/
│   └── figures/
│       └── .gitkeep
├── scripts/
│   └── scrape_moteur_ma.py
├── README.md
└── .gitignore
```

## Main Files

- [`scripts/scrape_moteur_ma.py`](scripts/scrape_moteur_ma.py): scraper for Moteur.ma used-car listings and detail pages
- [`notebooks/EDA.ipynb`](notebooks/EDA.ipynb): exploratory data analysis notebook
- [`data/raw/moteur_ma_listings.csv`](data/raw/moteur_ma_listings.csv): current dataset file

## Getting Started

### 1. Install dependencies

```bash
pip install requests beautifulsoup4
```

### 2. Run the scraper

```bash
python scripts/scrape_moteur_ma.py --resume
```

By default, the scraper saves new output to:

- `data/raw/moteur_ma_cars.jsonl`

Useful options:

- `--delay 1.0` to slow down requests
- `--max-pages 2` to test on a small number of pages
- `--output path/to/file.jsonl` to change the output path

## Notes

- The scraper is designed to be resumable.
- Generated JSONL outputs are ignored by git so the repository stays clean.
- The current CSV file is preserved in `data/raw/` as part of the project data.

## PDF Reference

The brief for this project is in:

- `Practical project_second_hand_car_price_SDBDIA2A.pdf`


# iPhone Duo Monitor 

[![iPhone Duo Inventory Check](https://github.com/josephgattuso/iphone-duo-monitor/actions/workflows/iphone-stock.yml/badge.svg)](https://github.com/josephgattuso/iphone-duo-monitor/actions/workflows/iphone-stock.yml)

A modest Python agent that automates Apple Store checks for shifts in iPhone Duo inventory.

## Features

- Searches all Apple Stores returned for a private postcode
- Prioritises the 512GB Night Sky model
- Optionally checks alternative colours and capacities
- Reports which nearby stores appear to have pickup stock
- Sends notifications through ntfy
- Runs automatically with GitHub Actions
- Keeps the postcode and ntfy topic out of the public repository
- Does not reserve a device or place an order

## How it works

On each run, the monitor:

1. Opens the Apple UK iPhone Duo purchase page.
2. Selects the preferred colour and storage capacity.
3. Opens the pickup availability search.
4. enters the postcode supplied through a private environment variable.
5. Checks every nearby store returned by Apple.
6. Repeats the search for alternative configurations when enabled.
7. Sends a private ntfy notification if pickup stock is detected.

The preferred configuration is checked first. Alternatives are checked in this order:

1. 512GB in Night Sky
2. Other capacities in Night Sky
3. 512GB in another colour
4. Remaining colour and capacity combinations

Preferred matches are labelled `PREFERRED MATCH`. All other matches are labelled `ALTERNATIVE`.

## Project structure

```text
.
├── .github/
│   └── workflows/
│       └── iphone-stock.yml
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── stock_monitor.py
```

## Privacy

This project is designed to be safe to publish, but you must configure it correctly. The postcode and ntfy topic should be stored as GitHub Actions secrets. The workflow passes them to the monitor only while it is running.

The script deliberately avoids printing the postcode or detailed nearby-store results to public GitHub Actions logs. Store details are sent through the private notification instead.

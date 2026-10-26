# iPhone Duo Pickup Stock Monitor

A small Python and Playwright agent that checks nearby Apple Stores for iPhone Duo pickup availability and sends a private push notification through ntfy.

The monitor prioritises the following configuration:

- **Colour:** Night Sky
- **Storage:** 512GB

If the preferred configuration is unavailable, the monitor can also check other colours and storage capacities.

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

## Privacy

This project is designed to be safe to publish, but you must configure it correctly.

Do not commit:

- Your postcode
- Your private ntfy topic
- A populated `.env` file
- Screenshots containing nearby store information
- Browser traces or HAR files
- Stock results tied to your location
- A `stock_state.json` file from an older version of the monitor

The postcode and ntfy topic should be stored as GitHub Actions secrets. The workflow passes them to the monitor only while it is running.

The script deliberately avoids printing the postcode or detailed nearby-store results to public GitHub Actions logs. Store details are sent through the private notification instead.

> [!IMPORTANT]
> If sensitive information was previously committed, adding it to `.gitignore` does not remove it from Git history. Remove it from the repository history or publish the project from a new, clean repository.

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

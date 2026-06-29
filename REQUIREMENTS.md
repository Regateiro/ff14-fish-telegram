# FFXIV Flying Fish

This file specifies the requirements of this project that must be achieved.

## Specifications

This is a telegram bot project that must be able to do the following:

- Using the https://github.com/icykoneko/ff14-fish-tracker-app tracker, monitor fish available for the game Final Fantasy XIV.
- Keep a database (sqlite) of fish caught per telegram user.
  - Users should be able to use the following commands to manage their list of caught fish:
    - `/caught <fish name>`, to mark a fish as caught. The argument `all` can be used to mark all fish as caught.
    - `/uncaught <fish_name>`, to mark a fish a uncaught. The argument `all` can be used to mark all fish as uncaught.
- Remind users when a fish window is about to be available for an uncaught fish (10mins before for fish that can be caught directly with mooching or fisher's intuition, otherwise 30mins before). Enabled by default.
- Use the command `/day` to receive a list of uncaught fish that will be available in the next 24 hours.

## Project

- The project should follow an MVP structure.
- Poetry should be used for dependency and virtual environment management.
- Make sure the project has linting and formatting tools.
  - Have a makefile with targets to run them.
- Tests should be created with high coverage to ensure that the code is working correctly.

## Telegram

To interact with Telegram, using the `TELEGRAM_TOKEN` available in the .env file.

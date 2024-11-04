# Maltego Telegram

![preview.png](https://github.com/user-attachments/assets/cc1ae1be-f54e-4578-bed8-e9fb70622682)

Maltego module for working with Telegram.

Features:

- Indexing of all stickers/emoji in Telegram channel
- Identification of the creator of a set of stickers/emoji

## Installation

1. Clone the repository

```
git clone https://github.com/vognik/maltego-telegram
```

2. Specify secrets in `config.ini`:
- `api_id` and `api_hash`: instructions [https://core.telegram.org/api/obtaining_api_id](https://core.telegram.org/api/obtaining_api_id)
- `bot_token`: instruction [https://core.telegram.org/bots/tutorial#obtain-your-bot-token](https://core.telegram.org/bots/tutorial#obtain-your-bot-token)
3. Execute the commands

```
pip install -r requirements.txt
python project.py
python login.py
```

4. Import `entities.mtz` and `maltego.mtz` files using Import Config in Maltego
5. Check if they work: new entities and their associated Transforms should appear in Entity Palette.

# Maltego Telegram

![preview.png](https://github.com/user-attachments/assets/5463e9a9-9db3-4b0d-a888-bd19f5190cac)

**Telegram Maltego** — a free set of Transforms for Maltego that enables OSINT investigations in the Telegram messenger.

Initially designed solely to simplify de-anonymization through stickers/emojis, it has since expanded far beyond its original functionality, allowing for more advanced investigations.

**Features:**

- Getting Telegram profile by phone number
- Getting a linked Telegram channel group
- Getting a list of Telegram group administrators
- Getting a list of authors of a Telegram channel
- Collect all forwarded & similar channels by Channel
- Search for deleted posts and generate links to view them
- Indexing of all stickers/emoji in Telegram channel
- Identification of the creator of a set of stickers/emoji

## How it works
Currently, there are over 10 available Transforms. A full list can be found in the directory of the same name, as well as in the Maltego program when you import them.

Here’s how some of these Transforms work.

### Stickers and their creators
![stickers.png](https://github.com/user-attachments/assets/d5ebb835-138f-4d4e-8b52-570dee9babb0)

Each Telegram user has their own UID.

Each sticker set that a user creates has its ID hidden in it.

To reveal it, my Transform executes the following algorithm:
1. Make an API request to get information about the sticker set
2. Take the value of the "ID" key from the response
3. Perform a binary shift by 32 to the right.

The resulting UID can be exchanged for a familiar login using the `@tgdb_bot` bot, and thus reveal the user's profile.

**The author of a channel who did not leave contacts can be de-anonymized. To do this, you need to scan his channel and find the sticker packs that he has ever created. My Transform for Maltego does this automatically.**

Find out more: [What's wrong with stickers in Telegram? Deanonymize anonymous channels in two clicks](https://hackernoon.com/whats-wrong-with-stickers-in-telegram-deanonymize-anonymous-channels-in-two-clicks)

### Similar channels
![similar.png](https://github.com/user-attachments/assets/87ff0649-3b8f-4e7c-85a7-1a5451230a6f)

Telegram has a built-in function to search for channels whose audience overlaps with the current one. 

Maltego makes the search more convenient by visualizing the results.

### Profiles that may be associated with the channel
![forwarded.png](https://github.com/user-attachments/assets/6f2d875a-c0d1-48da-b5c2-82a5912c1c71)

Administrators can forward their own messages and other users to their channel.

If a user has changed their privacy settings and removed the link to their account (Forwarded Messages = Nobody), this will only apply to forwarding their new messages.

Old forwarded messages will still link to their real profile.

### Deleted posts and their content
![deleted.png](https://github.com/user-attachments/assets/f3708918-4c9f-44f2-8be9-483e4f19cbea)

In Telegram, each post has a unique numeric ID, which increases with each new post. The first post in a channel has ID 1, the second post has ID 2, and so on. If there are gaps between post numbers, it means that some posts have been deleted.

There are services that index Telegram content. Even if a post has been deleted from Telegram, it may still be stored in these services.

This Transform helps you find deleted posts and creates links to view them in the archives.

## Installation

1. Clone the repository

```
git clone https://github.com/vognik/maltego-telegram
```

2. Install dependencies

```
pip install -r requirements.txt
```

3. Specify secrets in `config.ini`:
- `api_id` and `api_hash`: guide [https://core.telegram.org/api/obtaining_api_id](https://core.telegram.org/api/obtaining_api_id)
- `bot_token`: guide [https://core.telegram.org/bots/tutorial#obtain-your-bot-token](https://core.telegram.org/bots/tutorial#obtain-your-bot-token)

4. Log in to Telegram

```
python login.py
```

5. Generate Transforms Import File

```
python project.py
```

6. Import `entities.mtz` and `telegram.mtz` files using Import Config in Maltego
7. Check if they work: new Entities and Transforms should appear in Maltego

![imports.png](https://github.com/user-attachments/assets/e9ce7b6f-b14e-4239-83cd-2510ac3db9d5)


## Usage
Drag and drop an entity from the Entity Pallete, right-click and select the desired Transform.

https://github.com/user-attachments/assets/1fa23899-fd52-435f-830b-0df27cb65439

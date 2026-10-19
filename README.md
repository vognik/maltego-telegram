<h4 align="center">Maltego-powered OSINT tool for investigating Telegram<br></h4>

---

<p align="center">
<img src="static/maltego-telegram.png" alt="maltego-telegram" width="500px">
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#install">Install</a> •
  <a href="#usage">Usage</a>
</p>

---

**Maltego Telegram** is an OSINT utility that enables investigations on Telegram through a collection of Maltego Transforms. It brings Telegram data into Maltego, helping investigators explore connections and visualize relationships. Maltego Telegram is built for one thing — Telegram investigations — and makes them simple and intuitive.

# Features

## Sticker and emoji pack owners

<h1 align="left">
  <img src="static/stickers.png" alt="maltego-telegram"></a>
  <br>
</h1>

Sticker and custom emoji packs can provide another way to identify their creators.
- Identify the account associated with a pack’s creation.
- Resolve the creator’s profile when accessible.
- Map the connection between the pack and its creator in Maltego.

A creator’s account can provide a link between otherwise unrelated packs.

## Similar channels

<h1 align="left">
  <img src="https://github.com/user-attachments/assets/87ff0649-3b8f-4e7c-85a7-1a5451230a6f" alt="maltego-telegram"></a>
  <br>
</h1>

Telegram displays related channels as a list. Mapping these recommendations in Maltego makes their connections easier to explore.

- Retrieve channel recommendations through the Telegram API.
- Display channels as entities connected by recommendation links.
- Expand the graph to identify groups of related channels.

Expand recommendations from multiple channels to find shared connections.

## Profiles linked to a channel

<h1 align="left">
  <img src="https://github.com/user-attachments/assets/6f2d875a-c0d1-48da-b5c2-82a5912c1c71" alt="maltego-telegram"></a>
  <br>
</h1>

Forwarded messages may contain references to their original authors. These can reveal personal profiles associated with a channel.
- Inspect forwarding metadata for references to user accounts.
- Resolve accessible author profiles.
- Connect those profiles to the channel in Maltego.

Older forwards may retain author links after privacy settings change.

## Deleted posts and archived content

<h1 align="left">
  <img src="https://github.com/user-attachments/assets/f3708918-4c9f-44f2-8be9-483e4f19cbea" alt="maltego-telegram"></a>
  <br>
</h1>

Telegram assigns sequential numeric IDs to channel messages. Gaps in the sequence can help locate potentially deleted posts.
- Detect missing IDs in a channel’s message history.
- Check public Telegram archives for matching channel and post IDs.

Archived copies may include the original text, media, and publication date.

---

There’s more to explore. Browse the [full collection of Transforms](https://github.com/vognik/maltego-telegram/tree/main/transforms) for additional capabilities.

# Install

1. Clone the repository
```bash
git clone https://github.com/vognik/maltego-telegram
cd maltego-telegram
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure Telegram API credentials

Obtain your `api_id` and `api_hash` from [Telegram](https://core.telegram.org/api/obtaining_api_id), then add them to `config.ini`.


4. Log in to Telegram
```bash
python login.py
```

Follow the prompts to authenticate your Telegram account.

5. Generate Maltego Transform files
```bash
python project.py
```

6. Import into Maltego

In Maltego, open **Import Config** and import both generated files:
- `entities.mtz`
- `telegram.mtz`

![imports](https://github.com/user-attachments/assets/e9ce7b6f-b14e-4239-83cd-2510ac3db9d5)

# Usage

1. Drag an entity from the **Entity Palette** onto the graph.
2. Right-click the entity to view available Transforms.
3. Select a Transform to run it.

https://github.com/user-attachments/assets/dba4b5b1-a82d-4e26-b8e4-d063f5456f88

## License

Maltego Telegram is licensed under the [GNU General Public License v3.0](README.md).

Built for the OSINT community. Contributions, ideas, and feedback are welcome.

Use responsibly and only for lawful investigations.

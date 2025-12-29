# 🔎 Maltego Telegram  
**OSINT Transforms for Telegram investigations**

![preview](https://github.com/user-attachments/assets/5463e9a9-9db3-4b0d-a888-bd19f5190cac)

**Maltego Telegram** is a free set of Maltego Transforms designed for OSINT investigations in the Telegram messenger.

The project originally focused on de-anonymization via stickers and emoji, but has since evolved into a full-featured toolkit for analyzing Telegram channels, groups, and user profiles.

---

## 🚀 Features

With Maltego Telegram you can:

- 📱 Retrieve a Telegram profile by phone number  
- 👥 Discover groups and chats linked to a Telegram channel  
- 🛡 Get a list of Telegram group administrators  
- ✍️ Identify authors of Telegram channels  
- 🔁 Collect forwarded and audience-overlapping (similar) channels  
- 🗑 Detect deleted posts and generate links to archived content  
- 😀 Index all stickers and emoji used in a Telegram channel  
- 🧩 Identify creators of sticker and emoji packs  

More than **10 Transforms** are currently available.  
A full list can be found:
- in the `Transforms` directory  
- directly in Maltego after importing the project

---

## 🧠 How it works

Below are some key investigation scenarios enabled by the Transforms.

---

### 😀 Stickers and their creators  

![stickers](https://github.com/user-attachments/assets/d5ebb835-138f-4d4e-8b52-570dee9babb0)

Every Telegram user has a unique **UID**.  
When a user creates a sticker pack, this UID is **embedded inside the pack ID**.

The Transform extracts it using the following logic:

1. Request sticker pack metadata via the Telegram API  
2. Extract the value of the `id` field  
3. Perform a 32-bit right binary shift  

The resulting UID can be resolved to a username (for example, via the `@tgdb_bot`).

📌 **Practical use case**  
If a channel author does not provide contact details, they can be de-anonymized by scanning the channel for sticker packs they have created.  
Maltego Telegram performs this process automatically.

🔗 Read more:  
[What's wrong with stickers in Telegram? Deanonymize anonymous channels in two clicks](https://hackernoon.com/whats-wrong-with-stickers-in-telegram-deanonymize-anonymous-channels-in-two-clicks)

---

### 🔗 Similar channels  

![similar](https://github.com/user-attachments/assets/87ff0649-3b8f-4e7c-85a7-1a5451230a6f)

Telegram provides a built-in feature for discovering channels with overlapping audiences, but the results are shown only as a list.

Maltego enhances this by:
- visualizing relationships,
- revealing channel networks,
- simplifying ecosystem-level analysis.

---

### 🔁 Profiles associated with a channel  

![forwarded](https://github.com/user-attachments/assets/6f2d875a-c0d1-48da-b5c2-82a5912c1c71)

Channel administrators often:
- forward their own messages,
- repost content from personal accounts.

Even if a user later restricts forwarding (`Forwarded Messages = Nobody`), **older forwarded messages remain linked to the original profile**.

This Transform:
- detects such messages,
- connects channels to real user profiles.

---

### 🗑 Deleted posts and archived content  

![deleted](https://github.com/user-attachments/assets/f3708918-4c9f-44f2-8be9-483e4f19cbea)

Each Telegram post has a sequential numeric ID:
- 1, 2, 3, 4 …

Missing IDs indicate that posts were deleted.

This Transform:
- detects gaps in post IDs,
- checks public Telegram archives,
- generates links to preserved copies of deleted content.

---

## ⚙️ Installation

### 1️⃣ Clone the repository
```bash
git clone https://github.com/vognik/maltego-telegram
```

### 2️⃣ Install dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ Configure `config.ini`

Set the following values:
- `api_id` and `api_hash`  
  https://core.telegram.org/api/obtaining_api_id  
- `bot_token`  
  https://core.telegram.org/bots/tutorial#obtain-your-bot-token  

---

### 4️⃣ Log in to Telegram
```bash
python login.py
```

### 5️⃣ Generate Transform files
```bash
python project.py
```

---

### 6️⃣ Import into Maltego

Import the following files using **Import Config** in Maltego:
- `entities.mtz`
- `telegram.mtz`

![imports](https://github.com/user-attachments/assets/e9ce7b6f-b14e-4239-83cd-2510ac3db9d5)

---

## ▶️ Usage

1. Drag an entity from the **Entity Palette**
2. Right-click on it
3. Select the desired Transform

🎥 Demo:

https://github.com/user-attachments/assets/dba4b5b1-a82d-4e26-b8e4-d063f5456f88

---

## 📄 License

This project is licensed under the **GPL-3.0 license**.  
See the `LICENSE` file for details.

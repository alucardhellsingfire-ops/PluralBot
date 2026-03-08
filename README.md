# 💜 PluralCord

**A full-featured Discord bot for plural systems — built as a community replacement for Simply Plural.**

PluralCord brings system management directly into Discord with slash commands, message proxying, front tracking, journaling, per-member polls, and more.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🌟 System profiles | Name, tag, description, color, avatar, privacy settings |
| 👥 Member management | Add, edit, archive, group headmates with full profiles |
| ✨ Front tracking | Log switches, co-fronting, history, and visual analytics |
| 🏷️ Message proxying | Send messages as members via webhook (like PluralKit) |
| 📓 Journaling | Private or shared entries with tags and full-text search |
| 📊 Polls | Create polls where every member votes independently |
| 💜 Friends system | Friend other systems and see their current front |
| 📥 Data export | Full JSON export of all your system data |
| 🗂️ Groups | Organize members into subsystems/groups |
| 📝 Notes | Per-member notes for the system |

---

## 🚀 Setup Guide

### Step 1 — Create your Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → give it a name (e.g. "PluralCord")
3. Go to the **Bot** tab → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
5. Click **Reset Token** and copy your bot token — keep it secret!

### Step 2 — Invite the bot to your server

Go to **OAuth2 → URL Generator**, select:
- Scopes: `bot`, `applications.commands`
- Bot permissions:
  - ✅ Send Messages
  - ✅ Embed Links
  - ✅ Attach Files
  - ✅ Read Message History
  - ✅ Manage Webhooks *(needed for proxying)*
  - ✅ Use Slash Commands

Copy and open the generated URL to invite the bot.

### Step 3 — Run the bot

**Requirements:** Python 3.10+ — download from [python.org](https://www.python.org/downloads/) if you don't have it.
When installing, check the box that says **"Add Python to PATH"**.

Your bot files are already in the right place:
`C:\Users\Alynn\Desktop\PluralBot`

**Open PowerShell** (press Win + R, type `powershell`, hit Enter) and run these commands one at a time:

```powershell
# Navigate to your bot folder
cd C:\Users\Alynn\Desktop\PluralBot

# Install dependencies
pip install -r requirements.txt

# Set your bot token (replace the part in quotes with your actual token)
$env:DISCORD_TOKEN="paste-your-token-here"

# Run the bot!
python bot.py
```

You should see `PluralCord online as ...` in the console when it's working.

> **Note:** You'll need to set `$env:DISCORD_TOKEN` again each time you open a new PowerShell window.
> To avoid this, you can instead open `bot.py` in Notepad and replace `os.environ.get('DISCORD_TOKEN')`
> with your token in quotes directly — e.g. `token = "your-token-here"` — though keep that file private if you do.

The bot will sync slash commands on startup. This may take up to a minute to appear in Discord.

### Step 4 — First use

```
/system create My System
/member add Alice pronouns:she/her description:The host
/member add Bob pronouns:he/him
/front set Alice
```

---

## 📖 Command Reference

### System
| Command | Description |
|---|---|
| `/system create <name>` | Register your system |
| `/system view` | View your system profile |
| `/system edit` | Edit name, tag, description, color, avatar, privacy |
| `/system delete` | ⚠️ Delete all system data |
| `/system set-channel #channel` | Set front notification channel |
| `/system export` | Download all data as JSON |

### Members
| Command | Description |
|---|---|
| `/member add <name>` | Add a new member |
| `/member view <name>` | View a member's profile |
| `/member edit <name>` | Edit a member's details |
| `/member list` | List all members |
| `/member delete <name>` | Remove a member |
| `/member archive <name>` | Hide without deleting |
| `/member note <name> <note>` | Add a note |
| `/member notes <name>` | View member notes |

### Groups
| Command | Description |
|---|---|
| `/group create <name>` | Create a group/subsystem |
| `/group add-member <group> <member>` | Add member to group |
| `/group list` | List all groups |
| `/group delete <name>` | Delete a group |

### Fronting
| Command | Description |
|---|---|
| `/front set <member>` | Set current fronter (clears others) |
| `/front add <member>` | Add to co-front |
| `/front remove <member>` | Remove from co-front |
| `/front clear` | Clear the front |
| `/front view` | See who's fronting |
| `/front history` | View switch history |
| `/front stats` | Analytics with percentage bars |

### Proxying
| Command | Description |
|---|---|
| `/proxy set <member> [prefix] [suffix]` | Set proxy tags |
| `/proxy clear <member>` | Remove proxy tags |
| `/proxy list` | List all proxy configs |
| `/proxy test <member>` | Test your proxy setup |

> To proxy: if Alex has prefix `A:`, typing `A: Hello!` in chat sends as Alex via webhook.
> Requires **Manage Webhooks** permission in that channel.

### Journal
| Command | Description |
|---|---|
| `/journal write` | Open a form to write an entry |
| `/journal list` | List entries |
| `/journal view <id>` | Read an entry |
| `/journal delete <id>` | Delete an entry |
| `/journal search <query>` | Search by keyword or tag |

### Polls
| Command | Description |
|---|---|
| `/poll create <question> <opt1> <opt2>` | Create a poll |
| `/poll vote <id> <member> <option>` | Vote as a member |
| `/poll results <id>` | View results |
| `/poll close <id>` | Close a poll |
| `/poll list` | List active polls |

### Friends
| Command | Description |
|---|---|
| `/friends add @user` | Send friend request |
| `/friends accept @user` | Accept a request |
| `/friends pending` | View incoming requests |
| `/friends list` | Your friends list |
| `/friends front @user` | See their front |
| `/friends remove @user` | Unfriend |

---

## 🔒 Privacy

- All data is stored **locally** in a SQLite database (`pluralcord.db`) on the machine running the bot
- Data is scoped per Discord server — each server has its own records
- Members can be marked private; the system privacy can be set to `private` to hide from friends
- Nothing is shared with any third party
- Use `/system export` to download your data at any time

---

## 💡 Tips

- **Co-fronting:** Use `/front add` to have multiple members front at once
- **Proxying:** Needs `Manage Webhooks` permission in each channel. Check with `/proxy test`
- **Notifications:** Set a dedicated channel with `/system set-channel` to get front updates posted there
- **Groups:** Use `/group create` to organize your system (e.g. "Littles", "Protectors")
- **Archiving:** Instead of deleting old members, `/member archive` hides them while preserving history

---

## ❤️ Built for the plural community

PluralCord was built with love as a free, self-hosted alternative to Simply Plural.
The entire codebase is yours to use, modify, and share.

*You are valid. Your system is valid. 💜*

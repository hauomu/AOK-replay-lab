# TwoDie Handoff Draft

The bot is being built as an AoK community companion tool, not as a gameplay automation tool.

## Current MVP

- Accepts uploaded `.SC2Replay` files or small replay ZIPs.
- Parses map, duration, players, teams, unit/combat/style signals where available.
- Stores local stats in SQLite.
- Produces Discord-friendly reports and leaderboards.

## Minimum Discord install scopes

```text
bot
applications.commands
```

## Minimum permissions for replay-analysis MVP

```text
View Channels
Send Messages
Embed Links
Attach Files
Read Message History
Use Slash Commands
```

No admin or moderation permissions are required for the replay-analysis MVP.

## Optional future permission set for anti-spam module

Only needed if we later implement onboarding/spam protection:

```text
Manage Messages
Moderate Members
Manage Roles
```

## Future metadata request

The replay analyzer works without map source access, but reports become much better with an AoK metadata export:

- unit IDs to display names
- building IDs to display names
- ability IDs to action names
- upgrade IDs to tech names
- bank key meanings
- major trigger/objective labels
- cost/build-time/tech-tree data if available

This avoids needing TwoDie to build the bot himself while allowing the community tool to speak accurate AoK terminology.

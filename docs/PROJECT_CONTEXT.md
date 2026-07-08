# Project Context

This project started as an AoK replay-analysis experiment for **StarCraft II Arcade: Age of Knights**.

The near-term goal is not to build a live gameplay bot. The immediate goal is to build useful community tooling:

- replay upload analysis
- Discord-friendly match reports
- player profiles and leaderboards
- offline strategy mining
- guide-writing support based on replay evidence

## Deployment context

Sherman is a moderator in the AoK Discord server but does not currently have permission to deploy/install bots there. The development workflow is therefore:

1. Test the bot in Sherman's private Discord test server.
2. Produce a working demo.
3. Ask TwoDie/server owner to test-deploy the bot. 

## Scope separation

There are two future workflows:

1. Replay / SC2Arcade / strategy-analysis tooling.
2. Anti-spam / onboarding guard for the AoK Discord server.

This repository currently focuses on workflow 1. Anti-spam/onboarding is tracked as a later module.

---
title: "Agent-Led Setup Requirements"
date: 2026-06-25
topic: agent-led-setup
---

# Agent-Led Setup Requirements

## Summary

The installed Codex skill should guide a support operator from an unready local profile to a usable Telegram support corpus. When setup is missing or incomplete, the Agent Surface should lead the operator through profile configuration, profile-local Telegram API credentials, Telethon login, sync, crawl, index, and a final ready check before normal support questions.

---

## Problem Frame

Marketplace installation only makes the workflow available. A new operator can still hit a dead end when the profile exists without a usable Telegram session, when Telegram API credentials are missing, or when the corpus has not been synced and indexed.

The product promise is local-first support help from Codex. The first-run experience needs to make the next action obvious from inside Codex instead of requiring the operator to infer the CLI sequence or discover Telethon credential setup independently.

---

## Key Decisions

- **Agent-led setup is primary.** Codex is where the operator experiences the plugin after marketplace installation, so the skill should detect unready local state and guide the recovery path.
- **Profile-local credentials are the default credential path.** Telegram API ID and API hash should be stored with the local Support Profile so repeated use does not depend on shell environment setup.
- **Readiness means usable corpus, not saved config.** Setup is complete only when the operator can ask a normal support question against synced and indexed local data.

---

## Actors

- A1. **Support Operator:** The local human who installs the plugin, owns the Telegram account, supplies setup inputs, and approves any Telegram write.
- A2. **Agent Surface:** The Codex skill that detects setup state, asks for missing inputs, runs local commands, and explains the next safe action.
- A3. **Local Core:** The shared CLI and Python core that persists profile state, stores credentials and session data locally, accesses Telegram, crawls web seeds, and builds indexes.
- A4. **Telegram API:** The external Telegram developer credential and user-session boundary required for Telethon access.

---

## Requirements

**Setup Detection**

- R1. The Agent Surface must check whether the selected Support Profile exists before running support workflows.
- R2. The Agent Surface must distinguish missing profile config, missing credentials, missing Telegram session, unsynced Telegram history, uncrawled web seeds, missing index, and ready states.
- R3. The Agent Surface must explain the next required setup step in operator-facing language when the profile is not ready.

**Guided Profile Setup**

- R4. The setup flow must collect a profile name, Telegram chat identifier, and at least one website or blog seed before creating the Support Profile.
- R5. The setup flow must accept Telegram chat identifiers in common forms such as bare names, `@` handles, and `t.me` links.
- R6. The Agent Surface must preserve the local-first boundary by writing profile state outside the plugin source tree.

**Telegram Credentials And Login**

- R7. The setup flow must guide the operator to provide Telegram API ID and API hash values required for Telethon user-session access.
- R8. Telegram API credentials must be stored as sensitive profile-local state rather than in the repository or generated docs.
- R9. The login flow must use the profile-local credentials and leave the profile in a clear actionable state when credentials are missing, invalid, or cancelled.
- R10. A successful login must create or reuse a profile-local Telegram session for future reads and confirmed writes.

**Corpus Build And Ready State**

- R11. After login, the Agent Surface must guide the operator through syncing Telegram history, crawling configured seeds, and building the local index.
- R12. The ready check must verify that the profile has enough local state to answer support questions before presenting the workflow as ready.
- R13. If any corpus-build step fails, the Agent Surface must report the failed step and the next retry action without implying setup is complete.

**Normal Workflow Handoff**

- R14. Once the profile is ready, the Agent Surface should switch from setup guidance to normal analytics, search, and draft workflows.
- R15. Posting behavior remains confirmation-gated and must not be weakened by setup automation.

---

## Key Flows

- F1. First use after marketplace install
  - **Trigger:** The operator asks Codex to use the Telegram support plugin with no ready profile.
  - **Actors:** A1, A2, A3
  - **Steps:** Codex checks profile state, asks for missing setup inputs, runs local setup commands, and reports the next required action after each command.
  - **Outcome:** The operator is guided toward a ready profile instead of seeing a dead-end command failure.
  - **Covered by:** R1, R2, R3, R4, R11, R12

- F2. Credential setup and login
  - **Trigger:** The profile lacks Telegram API credentials or a usable Telegram session.
  - **Actors:** A1, A2, A3, A4
  - **Steps:** Codex explains the required Telegram developer credentials, stores the provided values as profile-local sensitive state, and runs the login flow.
  - **Outcome:** The profile has a local Telegram session or a clear error state the operator can fix.
  - **Covered by:** R7, R8, R9, R10

- F3. Corpus build to ready state
  - **Trigger:** The profile is configured and logged in but not ready for support questions.
  - **Actors:** A1, A2, A3
  - **Steps:** Codex runs sync, crawl, and index in order, then performs a ready check.
  - **Outcome:** The operator can ask normal support questions, or Codex reports the exact step that still needs attention.
  - **Covered by:** R11, R12, R13, R14

---

## Scope Boundaries

- Hosted OAuth, cloud authentication, and shared hosted storage are out of scope.
- Reusing Telegram Desktop or mobile sessions is out of scope.
- A CLI wizard may exist later, but it is not the primary first-run experience for this work.
- Multi-profile management beyond selecting or naming one profile is deferred.

---

## Dependencies / Assumptions

- Telethon user-session access requires Telegram API credentials and a local login flow.
- Profile-local credential storage must be treated as sensitive local state.
- The current local-first architecture keeps profile data under the operator's local support directory rather than in the plugin source tree.
- Setup guidance can run local CLI commands from the installed plugin package.

---

## Acceptance Examples

- AE1. **Covers R1, R2, R3.** Given no local profile exists, when the operator asks a support question, then Codex starts setup guidance instead of attempting search or drafting.
- AE2. **Covers R4, R5, R6.** Given the operator provides `t.me/mailioio` and a website seed, when setup runs, then the Support Profile stores a normalized chat and seed outside the source tree.
- AE3. **Covers R7, R8, R9.** Given profile-local Telegram API credentials are missing, when login is requested, then Codex explains how to provide them and does not report login as complete.
- AE4. **Covers R9, R10.** Given profile-local credentials are valid, when the operator completes the Telegram login prompt, then the profile has a reusable local Telegram session.
- AE5. **Covers R11, R12, R13.** Given setup and login succeed, when Codex builds the corpus, then it runs sync, crawl, and index before reporting the profile ready.
- AE6. **Covers R14, R15.** Given the profile is ready, when the operator asks for a draft reply, then Codex follows the normal evidence and confirmation workflow.

---

## Success Criteria

- A new marketplace installer can reach a usable support corpus from Codex without manually discovering the CLI command sequence.
- Missing credentials produce a guided setup path rather than a generic unsupported Telegram error.
- The ready state is based on local profile, Telegram session, synced history, crawled seeds, and index availability.
- Profile-local credentials and session files are never written into the repository.

---

## Sources / Research

- `README.md` documents marketplace installation and the current manual setup sequence.
- `skills/telegram-support/SKILL.md` defines the Codex Agent Surface and local CLI boundary.
- `tg_support/cli.py` currently exposes `setup`, `login`, `sync`, `crawl`, and `index` as separate local commands.
- `tg_support/config.py` defines Support Profile paths under the local support directory and normalizes chat identifiers.
- `tg_support/telegram_client.py` currently has a Telethon gateway boundary but does not yet provide real credential-backed login behavior.
- `docs/brainstorms/telegram-support-agent-requirements.md` states that setup should feel like install, configure a chat, log in once, and index data.

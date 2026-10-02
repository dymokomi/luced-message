# luced-message

A messaging client written in Luce. It works the way Apple Mail does, with a
mailbox sidebar, a classic message list and a reader, and it looks like luced-2d
and luced-3d: grey and orange docked panes, square icon buttons and monospace type.
Messages come from **sources**. Email is the first source, read over IMAP and sent
over SMTP. Mail syncs on a background thread, so the window never waits on the
network.

```sh
luc install dymokomi/luced-message
# Or, from a development checkout:
luc run --release
```

Mailbox › Accounts… (Cmd/Ctrl-,) adds an account. You need the address, the
password (use an app password for Gmail, iCloud and Fastmail), the IMAP server
(port 993, `tls`) and the SMTP server (port 587, `starttls`, or 465, `tls`). TLS
1.3 is handled natively by [luce-tls](https://github.com/dymokomi/luce-tls).
Gmail, iCloud, Outlook and Fastmail all complete the handshake.

## Using it

| Action | Keys | Toolbar |
| --- | --- | --- |
| Get Mail | Cmd/Ctrl-Shift-N | get-mail |
| New Message | Cmd/Ctrl-N | compose |
| Reply / Reply All / Forward | Cmd/Ctrl-R / Cmd/Ctrl-Shift-R / Cmd/Ctrl-Shift-F | reply, reply-all, forward |
| Archive | Cmd/Ctrl-Alt-A | archive |
| Delete (to Trash) | Delete, Backspace | trash |
| Move to Junk | Cmd/Ctrl-Shift-J | junk |
| Flag / Mark as Unread | Cmd/Ctrl-Shift-L / Cmd/Ctrl-Shift-U | flag, mail-unread |
| Command Palette | Cmd/Ctrl-Shift-P | |

- **Message list:** newest first by date. A blue dot marks an unread message, a
  yellow flag a flagged one, and `@` one with attachments.
- **Search:** the search field narrows the list by sender and subject.
- **Reader:** shows the plain-text body, or HTML mail as readable text. Each
  attachment has a button that saves it.
- **Status line:** at the bottom of the window, it reports syncing, sending and
  failures.

## How it works

The [design notes](docs/DESIGN.md) give the whole picture. In short:

- **Protocol packages:**
  - [luce-mime](https://github.com/dymokomi/luce-mime) parses and writes messages.
  - [luce-imap](https://github.com/dymokomi/luce-imap) reads mail.
  - [luce-smtp](https://github.com/dymokomi/luce-smtp) sends it.
  - All three are luce-base.
- **The mail engine:** each account has its own thread running a Base engine
  (`src/mail_sync.lucb`). It keeps one IMAP session and syncs every folder: new
  headers, everyone's flags, and expunges. It fetches INBOX's newest bodies ahead
  of time, then waits in IDLE. Commands from the window run between those steps.
- **The store:** the engine writes `~/.luced-message/store`, and the window only
  ever reads it. Each folder has an index of its messages and the `.eml` files
  fetched so far. Events tell the window what changed.
- **Sources:** the window works with `Source` (`src/sources.luc`). EmailSource is
  the first kind; JMAP, Matrix or RSS would implement the same interface.

## Develop

```sh
python3 tests/run.py                       # headless tests
tools/test-server.sh && tools/seed.py      # a local GreenMail with mail for alice@example.test
python3 tools/preview.py --home DIR        # a real frame of the window, synced, as build/preview.png
```

To use the local server, create `DIR/accounts.toml` with:

```toml
[local]
address = "alice@example.test"
imap_host = "127.0.0.1"
imap_port = 3143
imap_security = "plain"
smtp_host = "127.0.0.1"
smtp_port = 3025
smtp_security = "plain"
password = "secret"
```

Then run `luced-message --home DIR`.

## Not yet

- The password is kept in `accounts.toml`; it should move to the system keychain.
- OAuth2 sign-in for Gmail and Outlook. The protocol side, XOAUTH2, is ready.
- Conversation threading.
- Server-side search.
- Drafts saved to the server.
- Multiple selection.
- HTML rendering through luce-browser-engine.
- TLS 1.2-only servers.
- East Asian wide characters need two cells in luce-ui's monospace layout.

## License

Dual-licensed under Apache-2.0 or MIT, at your option. Icons are from
luciaos-assets (CC BY 4.0).

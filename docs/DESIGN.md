# luced-message design

luced-message is a messaging client with the working habits of Apple Mail. It has
a mailbox sidebar, a message list and a reader, plus a separate compose window. It
is built on luce-ui in the style of luced-2d and luced-3d: docked panes, square
icon buttons, the grey and orange palette, monospace type. It is a bit old school
on purpose.

Messages come from **sources**. Email (IMAP to read, SMTP to send) is the first
source. Others, such as JMAP, Matrix or RSS, plug in behind the same interface,
and the UI never names a protocol.

## Packages

| Package | Language | Owns |
| --- | --- | --- |
| `luce-mime` | luce-base | RFC 5322 messages and MIME: header parsing and unfolding, RFC 2047 encoded words, RFC 2231 parameters, address lists, dates, the multipart tree, base64 and quoted-printable, charset decoding to UTF-8, a text view of a body (text/plain, or HTML turned into text), and building outgoing messages. |
| `luce-imap` | luce-base | An IMAP4rev1/IMAP4rev2 client: the response grammar (atoms, quoted strings, literals, lists, NIL), the session state machine, LOGIN and AUTHENTICATE PLAIN/XOAUTH2, LIST, SELECT/EXAMINE, STATUS, UID FETCH/SEARCH/STORE/COPY/MOVE/EXPUNGE, APPEND, IDLE, ENVELOPE and BODYSTRUCTURE. CONDSTORE/QRESYNC come later. |
| `luce-smtp` | luce-base | An SMTP submission client: EHLO and its extensions, STARTTLS, AUTH PLAIN/LOGIN/XOAUTH2, MAIL/RCPT/DATA with dot-stuffing, SIZE, 8BITMIME, SMTPUTF8, and the reply codes. |
| `luced-message` | Luce (+ a Base worker) | The application: sources, the local store, the sync worker and the UI. |

The owner chose three protocol packages instead of one `luce-mail`. Each format
owns its own reading and writing (the package boundaries rule). luce-imap and
luce-smtp do not depend on luce-mime: they move bytes and protocol structures,
and the application joins them together.

What we reuse:

- **luce-std**: `net` (resolver, `Connection`, `Deadline`, `Poller`), `files`,
  `paths`, `utf8`.
- **luce-tls**: TLS for implicit TLS (993/465) and STARTTLS (143/587). It is being
  extended in parallel with AES-GCM, RSA, a Mozilla root store, general chain
  building and a `Reader`/`Writer` stream type. Until then, the pinned self-signed
  path covers the local test server.
- **luce-crypto**: base64 for SASL comes from luce-mime's codec, not a copy.
- **luce-browser-foundation**: `text_codec` for legacy charsets (ISO-8859-x,
  Windows-125x, Shift_JIS, GBK, EUC-KR, KOI8). It is a heavy dependency, so
  luce-mime decodes UTF-8, US-ASCII, ISO-8859-1 and Windows-1252 itself. Other
  charsets go through a decoder hook the application supplies from text_codec.
- **luce-prism**: the local store's mailbox indexes, as columnar documents.
- **luce-config**: settings and account files (TOML).
- **luce-ui**: DStack/Panel docking, TableView for the message list,
  ListView/tree for mailboxes, TextEditor (`read_only`, `wrap`) for the reader
  and the composer, Dialog, Command, Menu, CommandPalette.
- **luciaos-assets**: the shared SVG icons for the toolbar squares.
- Later, **luce-browser-engine**: HTML mail rendered properly, with remote content
  blocked.

## Architecture

```
 ┌──────────────────────────── main thread (Luce) ─────────────────────────────┐
 │  UI: Sidebar · MessageList · Reader · Composer · Toolbar · Dialogs          │
 │        │ reads                                    ▲ events (copied text)    │
 │        ▼                                          │                         │
 │  Library (local store view)  ◄── Sources ──► SyncBridge (interop.Worker)    │
 └────────────────────────────────────────────────────┼────────────────────────┘
                                                      │ commands (copied text)
 ┌────────────────────────── sync worker thread (Base) ─▼──────────────────────┐
 │  Engine: one Session per account → luce-imap / luce-smtp → net / luce-tls   │
 │          writes the store (raw .eml + mailbox index), reports what changed  │
 └──────────────────────────────────────────────────────────────────────────────┘
```

- **Luce objects never cross threads.** The UI and the worker exchange copied
  text packets through `interop.Worker`, as luced-3d's compute bridge does.
  Commands go one way (`sync account`, `fetch body`, `set flags`, `move`,
  `send`), and events come back (`mailbox changed`, `body ready`, `progress`,
  `error`).
- **The store is the source of truth for the UI.** The worker writes it, and the
  UI reads it after an event names what changed. If the network is gone, the
  window still shows everything already synced.
- **Blocking I/O lives only on the worker.** The UI thread never waits on a
  socket. Long waits (IMAP IDLE) use std `net` deadlines and the worker's
  cancellation, so quitting is prompt.

### Sources

```
interface Source            # Luce, in src/sources/source.luc
    kind() -> SourceKind     # email, later jmap/matrix/rss
    account() -> Account
    folders() -> list[Folder]                   # from the store
    messages(folder) -> MessageTable            # summaries from the store
    open(message) -> MessageView                # body from the store, or ask the worker
    act(action, messages)                       # read/flag/move/delete/archive/junk
    compose_reply(message, kind) -> Draft
    send(draft)
    refresh()
```

`EmailSource` implements it on top of the store and the sync bridge. The UI
works only with `Folder`, `MessageSummary`, `MessageView` and `Draft`, which are
plain Luce classes. A future source maps its own concepts onto them: a Matrix
room is a Folder, an event is a message.

### Local store

`~/.luced-message/` (tests use a temporary directory):

```
settings.toml                     window, layout, preferences
accounts.toml                     accounts: kind, name, address, servers, auth method
store/<account-id>/
    folders.prisma                folder list: path, delimiter, role, special-use, counts
    <folder-hash>/index.prism     columnar summary table (below)
    <folder-hash>/<uid>.eml       raw RFC 5322 bytes, as fetched
```

The mailbox index is a luce-prism document holding typed columns: `uid u32[N]`,
`flags u16[N]`, `date i64[N]`, `size u32[N]`, plus strings for `from`, `subject`
and `preview`, with `uidvalidity` and `uidnext` scalars. Loading 50,000 summaries
is one read of the columns. The message list sorts and filters on these columns.

**Secrets.** Passwords are not stored in `accounts.toml`. v1 keeps them in
`secrets` with mode 0600 for the local test server only. The next step is a
keychain module: the macOS Keychain, Windows Credential Manager and the Linux
Secret Service. It lands where the owner decides; it is probably a small
general package.

### Sync (v1)

Per folder:

1. `SELECT`, then read UIDVALIDITY, UIDNEXT and EXISTS. A changed UIDVALIDITY
   drops the folder's cache.
2. New mail: `UID FETCH last+1:* (UID FLAGS INTERNALDATE RFC822.SIZE ENVELOPE
   BODY.PEEK[HEADER.FIELDS (REFERENCES IN-REPLY-TO LIST-ID)])` appends rows.
3. Flags: `UID FETCH 1:* (FLAGS)`, replaced later by CONDSTORE `CHANGEDSINCE`.
4. Expunges: `UID SEARCH ALL` against the index removes the rows that are gone.
5. Bodies: `UID FETCH n BODY.PEEK[]` on demand when a message is selected, and
   prefetched for the newest messages.
6. INBOX is watched with IDLE when the server supports it. Other folders are
   polled.

The local action runs first and then goes into a queue. The queued command is
replayed when online, and a failure rolls the row back.

Previews come from the first text part of a fetched body. Rows without a body
show none until it arrives.

## The window

The default layout follows Apple Mail, in docked panes:

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [✉][↻] [✎] │ [⤶][⤶⤶][⤷] │ [⌫][⊘][⚑] │ [▣ Archive]     [ search…      ] │  toolbar: square icon buttons
├────────────┬───────────────────────────────┬─────────────────────────────┤
│ MAILBOXES  │ INBOX · 1,204 · 12 unread      │ From  Bob <bob@…>           │
│ ▾ Favorites│ ● ⚑ From      Subject    Date  │ To    alice@…               │
│   Inbox 12 │ ● Bob        Hello…     20:34  │ Date  Fri 2 Oct 2026 20:34  │
│   Sent     │   Carol      Re: plan   Thu    │ Subject Hello from Bob      │
│ ▾ alice@…  │   …                            │ ─────────────────────────── │
│   Inbox    │                                │ Hi Alice,                   │
│   Drafts   │                                │ this is a test.             │
│   Archive  │                                │                             │
│   Trash    │                                │ ▸ 1 attachment              │
├────────────┴───────────────────────────────┴─────────────────────────────┤
│ status: Synced alice@example.test 20:35 · 1 message sent                 │
└──────────────────────────────────────────────────────────────────────────┘
```

- **Toolbar**: Get Mail, Compose, Reply, Reply All, Forward, Delete, Junk, Flag,
  Archive, Move to…, and Search. These are square icon buttons from
  luciaos-assets, each bound to a Command with a shortcut and listed in the
  command palette.
- **Sidebar**: Favorites (unified Inbox, Sent, Flagged), then each account's
  folder tree, with unread counts. Special-use roles (\Inbox, \Sent, \Drafts,
  \Trash, \Junk, \Archive) choose the icons.
- **Message list**: the classic Mail layout as a TableView. Columns: unread dot,
  flag, attachment, From, Subject, Date (the date is relative). It sorts by any
  column and threads by References and In-Reply-To (later). Multi-select needs a
  TableView extension.
- **Reader**: a header block, then the body in a read-only wrapped TextEditor,
  then attachments with Save and Open. Quoted text is dimmed with decorations.
- **Composer**: a Dialog for now, a second window later. It has To, Cc, Bcc,
  Subject, From (the account), a plain-text body editor, attachments, Send, and
  Save Draft.
- Panes are docked panels with stable ids. The layout persists like luced-2d's,
  and Window → Reset Layout restores it.
- **Accounts dialog**: kind (Email), name, address, IMAP host/port/security,
  SMTP host/port/security, and the user name. Test Connection runs a real login
  on the worker.

## Testing

- **Packages**: `luce-base test` per module, both backends, as in luce-vector.
  luce-mime tests against an RFC and real-world corpus (committed .eml
  fixtures). luce-imap and luce-smtp test their parsers on recorded transcripts,
  and their sessions against a scripted loopback server in-process, so CI needs no
  network.
- **Local server**: `tools/test-server.sh` runs GreenMail in Docker, with IMAP
  3143, SMTP 3025, IMAPS 3993 and SMTPS 3465, and users
  `alice@example.test`/`bob@example.test` with password `secret`.
  `tools/seed.py` fills mailboxes from fixture messages. Dovecot comes later for
  stricter conformance (CONDSTORE, QRESYNC, SPECIAL-USE).
- **App**: headless tests of the store, the sources and the sync engine against
  the scripted server. `--smoke` renders three frames. A live run against the
  local server is checked by hand before each release.
- **Real providers** (Gmail, iCloud, Fastmail, Outlook) once luce-tls reaches
  general TLS 1.3. App passwords first, OAuth2 (XOAUTH2) afterwards.

## Build order

1. luce-mime: parse, decode, text view and build, with fixtures.
2. luce-imap: response parser, session, the commands above, tested against
   transcripts and the loopback server, then live against GreenMail.
3. luce-smtp: submission, tested the same way. A message sent through GreenMail
   arrives in Alice's INBOX.
4. luced-message: store and sync worker, then the window (sidebar, list,
   reader), then compose and send, then actions (flags, move, delete), then IDLE.
5. TLS to real providers, the keychain, OAuth2.
6. Threading, search (local, then IMAP SEARCH), HTML through the browser engine,
   notifications, and further sources.

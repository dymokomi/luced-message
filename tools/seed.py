#!/usr/bin/env python3
"""Fill the local test server (tools/test-server.sh) with mail for Alice: folders
(Sent, Drafts, Archive, Junk, Trash) and a spread of messages: plain and HTML,
attachments, non-ASCII headers, a thread, newsletters and a volume of filler.

    tools/seed.py [--count 60]

A development aid only; the application's own tests do not need a server."""
import argparse, imaplib, smtplib, time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--count", type=int, default=60)
arguments = parser.parse_args()

imap = imaplib.IMAP4("127.0.0.1", 3143)
imap.login("alice@example.test", "secret")
for folder in ["Sent", "Drafts", "Archive", "Junk", "Trash", "Projects", "Projects/Luce"]:
    imap.create(folder)

now = time.time()
def message(sender, subject, body, days=0.0, html=None, attachment=None, reply_to_id=None, to="Alice <alice@example.test>"):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = sender, to, subject
    m["Date"] = formatdate(now - days * 86400, localtime=True)
    m["Message-ID"] = make_msgid(domain="example.test")
    if reply_to_id:
        m["In-Reply-To"] = reply_to_id
        m["References"] = reply_to_id
    m.set_content(body)
    if html:
        m.add_alternative(html, subtype="html")
    if attachment:
        name, kind, data = attachment
        maintype, subtype = kind.split("/")
        m.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return m

def append(folder, m, flags=""):
    imap.append(folder, flags, None, m.as_bytes())

first = message("Carol Åberg <carol@example.org>", "Quarterly plan — draft", "Hi Alice,\n\nThe plan is attached. Café at ten?\n\nCarol", days=3,
                attachment=("plan.pdf", "application/pdf", b"%PDF-1.4\n% placeholder plan\n"))
append("INBOX", first, "(\\Seen)")
reply = message("Dave Ng <dave@example.org>", "Re: Quarterly plan — draft", "Looks good to me.\n\n> The plan is attached. Café at ten?", days=2.5, reply_to_id=first["Message-ID"])
append("INBOX", reply)
append("INBOX", message("Luce Weekly <news@luce.example>", "This week in Luce: luced-message",
       "Read it in a browser.", days=1,
       html="<html><head><style>p{color:red}</style></head><body><h1>This week in Luce</h1><p>A <b>mail client</b> joins luced-2d and luced-3d.</p>"
            "<ul><li>IMAP and SMTP in Luce Base</li><li>MIME parsing</li><li>Native TLS 1.3</li></ul><p>&copy; Luce &mdash; unsubscribe</p></body></html>"))
append("INBOX", message("=?UTF-8?B?55Sw5Lit?= <tanaka@example.jp>", "会議の件", "アリスさん、\n\n明日の会議は10時からです。\n\n田中", days=0.6), "(\\Flagged)")
append("INBOX", message("Ольга <olga@example.ru>", "Привет из Москвы", "Алиса, привет!\n\nКак дела?", days=0.3))
append("INBOX", message("GitHub <noreply@github.example>", "[dymokomi/luce-imap] CI passed on main", "All checks have passed.", days=0.05))
for n in range(arguments.count):
    append("INBOX", message(f"Robot {n % 7} <robot{n % 7}@example.net>", f"Report #{n + 1}: nightly build",
           f"Build {n + 1} finished.\n\nNothing to see here.", days=4 + n * 0.37), "(\\Seen)" if n % 3 else "")
for n in range(12):
    append("Archive", message("Old Friend <friend@example.com>", f"Archived letter {n + 1}", "From the archive.", days=40 + n * 9), "(\\Seen)")
append("Sent", message("Alice <alice@example.test>", "Re: Lunch?", "Sounds good, see you at noon.", days=1.2, to="Bob <bob@example.test>"), "(\\Seen)")
append("Junk", message("Prize Desk <winner@spam.example>", "YOU HAVE WON!!!", "Click here.", days=0.8))
append("Projects/Luce", message("Bob <bob@example.test>", "luced-message design review", "Notes from today's review.", days=0.9), "(\\Seen)")
imap.logout()

smtp = smtplib.SMTP("127.0.0.1", 3025)
smtp.send_message(message("Bob <bob@example.test>", "Fresh off SMTP", "This one came through SMTP just now.", days=0))
smtp.quit()
print("seeded")

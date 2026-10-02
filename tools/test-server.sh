#!/bin/sh
# A local mail server for development: GreenMail in Docker with IMAP on 3143, SMTP on
# 3025 (IMAPS 3993, SMTPS 3465), and two users, alice@example.test and
# bob@example.test, password `secret`. Mail sent to either lands in their INBOX.
# Fill Alice's mailboxes with tools/seed.py.
set -eu
docker rm -f luced-mail >/dev/null 2>&1 || true
exec docker run -d --name luced-mail \
    -e GREENMAIL_OPTS='-Dgreenmail.setup.test.all -Dgreenmail.hostname=0.0.0.0 -Dgreenmail.users=alice:secret@example.test,bob:secret@example.test -Dgreenmail.users.login=email' \
    -p 3025:3025 -p 3143:3143 -p 3465:3465 -p 3993:3993 greenmail/standalone:2.1.2

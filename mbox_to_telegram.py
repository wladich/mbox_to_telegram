#!/usr/bin/python3
# coding: utf-8
import asyncio
import mailbox
import types
from argparse import ArgumentParser
from io import BytesIO
from typing import Iterator

import telegram_send  # type: ignore[import-untyped]

MAX_MESSAGE_SIZE = 10_000


def get_last_processed_message(state_file: str) -> str | None:
    try:
        with open(state_file, encoding="ascii") as f:
            return f.read()
    except FileNotFoundError:
        return None


def update_last_processed_message(state_file: str, message_id: str) -> None:
    with open(state_file, "w", encoding="ascii") as f:
        f.write(message_id)


def iterate_unread_messages(
    mbox: mailbox.mbox, last_read_id: str | None
) -> Iterator[mailbox.mboxMessage]:
    seen_last_message = last_read_id is None
    for email in mbox:
        if seen_last_message:
            yield email
        else:
            if email["Message-Id"] == last_read_id:
                seen_last_message = True
    if not seen_last_message:
        raise ValueError(f"Message with id={last_read_id!r} not found in mbox.")


def send_message(date: str, subject: str, body: str) -> None:
    msg_lines = [
        "Local email message",
        date,
        subject,
        "",
        body,
    ]
    msg_text = "\n".join(msg_lines)
    msg_files = None
    if len(msg_text) > MAX_MESSAGE_SIZE:
        msg_file = BytesIO(msg_text.encode("utf-8"))
        msg_file.name = "message.txt"
        msg_files = [msg_file]
        msg_text = msg_text[:MAX_MESSAGE_SIZE] + "\n...message too long..."

    res = telegram_send.send(messages=[msg_text], pre=True, files=msg_files)
    if isinstance(res, types.CoroutineType):
        asyncio.run(res)


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--mbox", required=True, help="Path to mbox file")
    parser.add_argument(
        "--state",
        required=True,
        help="Path to state file (stores id of last sent message)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        default=False,
        help="Only count pending messages",
    )
    parser.add_argument(
        "-e",
        "--end",
        action="store_true",
        default=False,
        help="Skip all messages to end. Write id of last email to state file.",
    )
    conf = parser.parse_args()
    dry_run: bool = conf.dry_run
    skip_to_end: bool = conf.end

    mbox = mailbox.mbox(conf.mbox)
    if skip_to_end:
        last_processed_message = None
    else:
        last_processed_message = get_last_processed_message(conf.state)
    count = 0
    email = None
    for count, email in enumerate(
        iterate_unread_messages(mbox, last_processed_message), 1
    ):
        if dry_run or skip_to_end:
            continue
        msg_id = email["Message-Id"]
        send_message(email["Date"], email["Subject"], str(email.get_payload()))
        update_last_processed_message(conf.state, msg_id)
        break
    if dry_run:
        print("Pending messages:", count)
    elif skip_to_end:
        print("Skipped messages:", count)
        if email is not None:
            msg_id = email["Message-Id"]
            update_last_processed_message(conf.state, msg_id)
    else:
        print("Messages processed:", count)


if __name__ == "__main__":
    main()

"""
common/links.py — Deep Linking Utility for Telegram Messages

Design Rationale:
- Source Attribution: AI summaries are only as trustworthy as their verifiable sources.
  Every insight provided by Project Aura should include a direct clickable link to
  the original Telegram message.
- MTProto ID Translation:
  - Public chats: If a chat has a public handle `@username`, the link is `https://t.me/{username}/{message_id}`.
  - Private supergroups / channels: MTProto assigns them internal 64-bit IDs with a `-100` prefix
    (e.g. -1001987654321). Deep links (`t.me/c/...`) require stripping the `-100` prefix,
    yielding `https://t.me/c/1987654321/{message_id}`.
"""


def build_message_link(chat_id: int, message_id: int, username: str = None) -> str:
    """
    Constructs a clickable deep link to a specific Telegram message.

    Args:
        chat_id: The raw Telegram chat/channel identifier.
        message_id: The specific message sequential ID within that chat.
        username: The public chat handle if available (e.g., 'tech_news').

    Returns:
        A direct web link opening the message in the Telegram app or web client.
    """
    if username:
        # Public channel or group with an established handle
        return f"https://t.me/{username}/{message_id}"

    # Private supergroup / channel: normalize MTProto identifier
    internal_id = str(chat_id)
    if internal_id.startswith("-100"):
        internal_id = internal_id[4:]
    elif internal_id.startswith("-"):
        internal_id = internal_id[1:]

    return f"https://t.me/c/{internal_id}/{message_id}"

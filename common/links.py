def build_message_link(chat_id: int, message_id: int, username: str = None) -> str:
    """
    Constructs a clickable deep link to a specific Telegram message.
    """
    if username:
        # Public chat
        return f"https://t.me/{username}/{message_id}"
        
    # Private supergroup
    internal_id = str(chat_id)
    if internal_id.startswith("-100"):
        internal_id = internal_id[4:]
    elif internal_id.startswith("-"):
        internal_id = internal_id[1:]
        
    return f"https://t.me/c/{internal_id}/{message_id}"

"""
generate_session.py — Interactive QR Code Session String Generator

Design Rationale:
- Headless Server Authentication: Running Telegram client tools on remote headless
  servers typically fails when relying on interactive SMS or phone verification codes.
  Telethon's QR login provides a zero-friction, carrier-independent authentication method:
  the operator scans an ASCII QR code rendered directly in their terminal using their
  phone's official Telegram app.
- Portable StringSession: Instead of generating a binary `.session` SQLite database file
  on disk (which risk accidental commits or filesystem locking), this script exports an
  in-memory Telethon `StringSession` that can be stored securely in `.env`.
"""

import asyncio
import os
import qrcode
import getpass
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

load_dotenv()

api_id = int(os.environ['TELEGRAM_API_ID'])
api_hash = os.environ['TELEGRAM_API_HASH']


async def main():
    print("Connecting to Telegram MTProto gateway...")
    client = TelegramClient(
        StringSession(), 
        api_id, 
        api_hash,
        device_model="Desktop Client",
        system_version="Linux / POSIX",
        app_version="10.0"
    )
    await client.connect()

    print("\nRequesting QR Code authentication token...")
    qr = await client.qr_login()

    print("\n" + "=" * 55)
    print(" SCAN THIS QR CODE IN YOUR TELEGRAM APP")
    print(" Navigation: Settings -> Devices -> Link Desktop Device")
    print("=" * 55 + "\n")

    # Render QR code using high-contrast ASCII blocks directly in terminal
    qr_code = qrcode.QRCode()
    qr_code.add_data(qr.url)
    qr_code.print_ascii(invert=True)

    print("\nWaiting for device scan (timeout: 120s)...")
    try:
        await qr.wait(timeout=120)
    except SessionPasswordNeededError:
        # User has Two-Step Verification enabled on their Telegram account
        print("\nQR code scanned successfully! Telegram requires your Two-Step Verification password.")
        password = getpass.getpass("Enter your 2FA Password: ")
        await client.sign_in(password=password)
    except Exception as e:
        print(f"\nQR Code authentication expired or failed: {e}")
        await client.disconnect()
        return

    print("\n" + "=" * 55)
    print("SUCCESS! Here is your TELEGRAM_SESSION_STRING:")
    print("=" * 55)
    print(client.session.save())
    print("=" * 55)
    print("Copy the string above and paste it into TELEGRAM_SESSION_STRING in your .env file.\n")

    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())

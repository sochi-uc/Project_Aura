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
    print("Connecting to Telegram...")
    client = TelegramClient(
        StringSession(), 
        api_id, 
        api_hash,
        device_model="Windows PC",
        system_version="Windows 11",
        app_version="10.0"
    )
    await client.connect()

    print("\nRequesting QR Code Login...")
    qr = await client.qr_login()
    
    print("\n" + "="*50)
    print("SCAN THIS QR CODE IN YOUR TELEGRAM APP")
    print("Go to: Settings -> Devices -> Link Desktop Device")
    print("="*50 + "\n")
    
    qr_code = qrcode.QRCode()
    qr_code.add_data(qr.url)
    qr_code.print_ascii(invert=True)
    
    print("\nWaiting for you to scan...")
    try:
        await qr.wait(timeout=120)
    except SessionPasswordNeededError:
        print("\nQR code scanned successfully! Telegram requires your 2FA password to finish.")
        password = getpass.getpass("Please enter your Two-Step Verification Password: ")
        await client.sign_in(password=password)
    except Exception as e:
        print(f"\nQR Code expired or failed: {e}")
        await client.disconnect()
        return

    print("\n" + "="*50)
    print("SUCCESS! Here is your TELEGRAM_SESSION_STRING:")
    print("="*50)
    print(client.session.save())
    print("="*50)
    print("Copy the long string above and paste it into your .env file!")
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())

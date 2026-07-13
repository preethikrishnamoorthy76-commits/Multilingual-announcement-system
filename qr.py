import qrcode
from qrcode.constants import ERROR_CORRECT_H

def generate_qr(link: str, filename: str = "telegram_qr.png",
                box_size: int = 8, border: int = 4):
    """
    Generate and save a QR code PNG for the given link.
    """
    qr = qrcode.QRCode(
        version=None,  # automatic size
        error_correction=ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(link)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)
    print(f"Saved QR to {filename} (link encoded: {link})")

if __name__ == "__main__":
    # Option A: web-friendly link (recommended for general use)
    web_link = "https://t.me/Multilingotrain_bot?send=C83RWI9E"

    # Option B: direct Telegram app link (works on mobile if tg:// is supported)
    # app_link = "tg://resolve?domain=Multilingotrain_bot&start=hi"

    generate_qr(web_link, "multilingotrain_hi_qr.png")
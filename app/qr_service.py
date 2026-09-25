import io
import base64
import qrcode
import qrcode.image.svg

def generate_qr_base64_png(data: str, box_size: int = 8, border: int = 2) -> str:
    """
    Generates a PNG QR code and encodes it as a Base64 Data URI.
    Perfect for inline rendering in HTML templates without extra round-trips.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64_str}"

def generate_qr_png_bytes(data: str, box_size: int = 10, border: int = 2) -> bytes:
    """
    Returns raw PNG bytes for direct HTTP response streaming.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def generate_qr_svg(data: str, box_size: int = 10, border: int = 2) -> str:
    """
    Generates an SVG QR code string. Scalable and crisp for printing.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
        image_factory=qrcode.image.svg.SvgPathImage,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image()
    
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")

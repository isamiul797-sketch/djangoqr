from django.shortcuts import render
from .models import QRCode
import qrcode
from django.core.files.storage import FileSystemStorage
from io import BytesIO
from django.core.files.base import ContentFile
from django.conf import settings
from pathlib import Path
import cv2
import numpy as np


def generate_qr(request):
    qr_image_url = None
    if request.method == 'POST':
        mobile_number = request.POST.get('mobile_number')
        data = request.POST.get('qr_data')

        # Validate mobile number
        if not mobile_number or len(mobile_number) != 10 or not mobile_number.isdigit():
            return render(request, 'scanner/generate.html', {'error': 'Invalid mobile number'})

        # Generate QR code content
        qr_content = f"{data}|{mobile_number}"
        qr = qrcode.make(qr_content)

        qr_image_io = BytesIO()
        qr.save(qr_image_io, format='PNG')
        qr_image_io.seek(0)

        # Define storage location
        qr_storage_path = settings.MEDIA_ROOT / 'qr_codes'
        fs = FileSystemStorage(location=qr_storage_path, base_url='/media/qr_codes/')
        filename = f"{data}_{mobile_number}.png"

        qr_image_content = ContentFile(qr_image_io.read(), name=filename)
        file_path = fs.save(filename, qr_image_content)

        qr_image_url = fs.url(file_path)

        # Save QR code info to database
        QRCode.objects.create(data=data, mobile_number=mobile_number)

    return render(request, 'scanner/generate.html', {'qr_image_url': qr_image_url})


def scan_qr(request):
    result = None
    if request.method == 'POST' and request.FILES.get('qr_image'):
        mobile_number = request.POST.get('mobile_number')
        qr_image = request.FILES['qr_image']

        # Validate mobile number
        if not mobile_number or len(mobile_number) != 10 or not mobile_number.isdigit():
            return render(request, 'scanner/scan.html', {'error': 'Invalid mobile number'})

        # Save uploaded image temporarily
        fs = FileSystemStorage()
        filename = fs.save(qr_image.name, qr_image)
        image_path = fs.path(filename)

        try:
            # Read image with OpenCV (handle unicode paths)
            img_array = np.fromfile(image_path, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            detector = cv2.QRCodeDetector()
            data, bbox, _ = detector.detectAndDecode(img)

            if data:
                # Split the data
                qr_date, qr_mobile_number = data.split('|')

                # Check database for matching entry
                qr_entry = QRCode.objects.filter(data=qr_date, mobile_number=qr_mobile_number).first()

                if qr_entry and qr_mobile_number == mobile_number:
                    result = "Scan success: Valid QR Code for the provided mobile number"
                    qr_entry.delete()

                    # Delete the QR code image file from media if exists
                    qr_image_path = settings.MEDIA_ROOT / 'qr_codes' / f"{qr_date}_{qr_mobile_number}.png"
                    if qr_image_path.exists():
                        qr_image_path.unlink()

                else:
                    result = "Scan Failed: Invalid QR code or mobile number mismatch"
            else:
                result = "No QR Code detected in the image"

        except Exception as e:
            result = f"Error processing the image: {str(e)}"

        finally:
            # Delete uploaded image after processing
            if fs.exists(filename):
                fs.delete(filename)

    return render(request, 'scanner/scan.html', {'result': result})

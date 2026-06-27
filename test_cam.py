import cv2
try:
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        print("Camera opened successfully.")
        ret, frame = cap.read()
        if ret:
            print("Successfully captured a frame.")
        else:
            print("Failed to capture frame.")
        cap.release()
    else:
        print("Failed to open camera.")
except Exception as e:
    print(f"Error: {e}")

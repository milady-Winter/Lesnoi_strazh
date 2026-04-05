import time
import json
import numpy as np
import cv2
from picamera2 import PiCamera2
from socket_sender import SocketSender


def calculate_angle(corners):
    """
    Calculates the rotation angle of the marker in degrees.
    Uses the vector between the top-left (0) and top-right (1) corners.
    """
    # corners[0] contains the 4 corner points of the marker
    p1 = corners[0][0]
    p2 = corners[0][1]

    delta_x = p2[0] - p1[0]
    delta_y = p2[1] - p1[1]

    # Calculate angle in degrees using arctan2
    angle = np.degrees(np.arctan2(delta_y, delta_x))
    return round(angle, 2)


def main():
    # Configuration
    WIDTH, HEIGHT = 640, 480
    PORT = 5005
    TARGET_ID = 0

    # Step 1: Initialize RPi5 Camera via picamera2
    picam2 = PiCamera2()
    config = picam2.create_preview_configuration(
        main={"format": 'RGB888', "size": (WIDTH, HEIGHT)}
    )
    picam2.configure(config)
    picam2.start()

    # Step 2: Initialize ArUco Detector (OpenCV 4.8+ syntax)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    aruco_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

    # Initialize the socket communication helper
    sender = SocketSender(port=PORT)

    print(f"Landing system active. Target ArUco ID: {TARGET_ID}")

    try:
        while True:
            start_time = time.time()

            # Step 3: Capture frame from CSI camera
            frame = picam2.capture_array()

            # Detect markers in the current frame
            corners, ids, rejected = detector.detectMarkers(frame)

            # Default payload if no marker is found
            payload = {
                "status": "NO_MARKER",
                "dx": 0,
                "dy": 0,
                "angle": 0.0,
                "confidence": 0.0
            }

            # Step 4: Process data if Target ID is detected
            if ids is not None and TARGET_ID in ids:
                # Find the index of our specific marker
                idx = np.where(ids == TARGET_ID)[0][0]
                marker_corners = corners[idx]

                # Calculate marker center (average of 4 corners)
                m_center = np.mean(marker_corners[0], axis=0)
                mc_x, mc_y = m_center[0], m_center[1]

                # Frame center coordinates
                c_x, c_y = WIDTH // 2, HEIGHT // 2

                # Calculate offsets (dx, dy)
                dx = int(mc_x - c_x)
                dy = int(mc_y - c_y)
                angle = calculate_angle(marker_corners)

                payload["dx"] = dx
                payload["dy"] = dy
                payload["angle"] = angle
                payload["confidence"] = 1.0

                # Check landing conditions (within 10px threshold)
                if abs(dx) < 10 and abs(dy) < 10:
                    payload["status"] = "LAND"
                else:
                    payload["status"] = "ADJUSTING"

            # Step 6: Send JSON data to Wexler via local socket
            sender.send(payload)

            # Step 7: Maintain 100ms cycle (10Hz frequency)
            elapsed = time.time() - start_time
            sleep_time = max(0, 0.1 - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\nShutting down landing system...")
    finally:
        picam2.stop()


if __name__ == "__main__":
    main()

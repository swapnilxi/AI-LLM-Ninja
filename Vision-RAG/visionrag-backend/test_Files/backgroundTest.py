# Simple background test that uses InputLayer from GestureDetection
import cv2
from pathlib import Path
import importlib.util

# Try a normal import first (works if GestureDetection is on PYTHONPATH)
try:
    from GestureDetection.camera_and_input_layer import InputLayer
except Exception:
    # Fallback: load module by file path relative to this test file
    repo_root = Path(__file__).resolve().parents[1]  # visionrag-backend
    module_path = repo_root / "GestureDetection" / "camera_and_input_layer.py"
    spec = importlib.util.spec_from_file_location("camera_and_input_layer", str(module_path))
    cam_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cam_mod)
    InputLayer = cam_mod.InputLayer


def main():
    # Use a fallback image that lives next to this test file (adjust path as needed)
    fallback = str(Path(__file__).resolve().parent / "fallback.jpg")
    inp = InputLayer(fallback, desired_width=1280, desired_height=720)

    while True:
        frame, source = inp.get_frame()

        # Overlay the source text
        cv2.putText(frame, f"Source: {source}", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        cv2.imshow("Background Test", frame)

        # Exit on ESC
        if cv2.waitKey(1) & 0xFF == 27:
            break

    inp.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

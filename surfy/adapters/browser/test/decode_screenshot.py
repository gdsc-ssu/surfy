import base64
from pathlib import Path
import sys
import webbrowser

def main():

    input_path = Path("./surfy/adapters/browser/test/test_screenshot.png")  # 기본값
    output_path = Path("./surfy/adapters/browser/test/decoded_screenshot.png")

    data = input_path.read_bytes()

    try:
        # base64 → bytes 디코딩 시도
        decoded = base64.b64decode(data)
        output_path.write_bytes(decoded)
        print(f"[OK] 디코딩 후 저장: {output_path.absolute()}")
    except Exception:
        # 이미 바이너리 PNG일 수도 있음
        output_path.write_bytes(data)
        print(f"[INFO] base64 아님, 원본 그대로 저장")

    # 자동으로 열기
    webbrowser.open(output_path.absolute().as_uri())


if __name__ == "__main__":
    main()

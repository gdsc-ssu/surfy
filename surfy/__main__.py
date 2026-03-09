import sys

from main import main

if __name__ == "__main__":
    command = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("명령을 입력하세요: ")
    main(command)
# 숭실대 소프트웨어학부의 교과과정에 대해 보고서를 md파일 형식으로 작성해
import os
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path, override=True)

user = os.getenv("DB_USER")
password = os.getenv("DB_PASSWORD")
host = os.getenv("DB_HOST")
database = os.getenv("DB_NAME")

# Mã hóa mật khẩu để xử lý ký tự đặc biệt (như @, #, !)
safe_password = urllib.parse.quote_plus(password) if password else ""

DB_URL = f"mysql+mysqlconnector://{user}:{safe_password}@{host}/{database}"
engine = create_engine(DB_URL)

if __name__ == "__main__":
    try:
        with engine.connect() as conn:
            print(">>> KẾT NỐI DATABASE THÀNH CÔNG!")
    except Exception as e:
        print(f">>> LỖI KẾT NỐI: {e}")
        
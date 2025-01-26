from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

# 環境変数の読み込み
load_dotenv(dotenv_path="/Users/iwamurahayato/myproject/Step4_POS-app_backend/.env.local")

# 必須の環境変数を取得
def get_env_variable(key: str) -> str:
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment variable '{key}' is not set.")
    return value

# デバッグ用ログ出力
print("DB_PASSWORD before encoding:", os.getenv("DB_PASSWORD"))

# データベース接続情報
DB_USER = get_env_variable('DB_USER')
DB_PASSWORD = quote_plus(get_env_variable('DB_PASSWORD'))  # パスワードをURLエンコード
DB_HOST = get_env_variable('DB_HOST')
DB_PORT = get_env_variable('DB_PORT')
DB_NAME = get_env_variable('DB_NAME')

# SSL証明書のパス
SSL_CERT_PATH = os.getenv('SSL_CERT_PATH')
if not SSL_CERT_PATH:
    print("Warning: SSL_CERT_PATH is not set.")

# デバッグ用ログ出力
print("Encoded DB_PASSWORD:", DB_PASSWORD)

# MySQLのURL構築
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# エンジンの作成
engine = create_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "ssl": {
            "ca": SSL_CERT_PATH or "/path/to/default/certificate.pem"  # デフォルト値を設定
        }
    }
)

# 接続テスト
try:
    with engine.connect() as connection:
        print("Secure connection successful with SQLAlchemy!")
except Exception as e:
    import traceback
    print("Secure connection failed:")
    traceback.print_exc()

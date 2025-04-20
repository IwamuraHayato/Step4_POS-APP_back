from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

ssl_test_path = r"C:\Users\daisu\SSL\DigiCertGlobalRootCA.crt.pem"
print("✅ 手動パス検証:", os.path.isfile(ssl_test_path))

# 環境変数の読み込み
load_dotenv()

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
SSL_CERT_PATH = os.getenv('SSL_CERT_PATH', '/etc/ssl/certs/ca-certificates.crt')
if not SSL_CERT_PATH:
    print("Warning: SSL_CERT_PATH is not set.")
ssl_ca = os.getenv("SSL_CERT_PATH")
print("✅ SSL_CA path:", ssl_ca)
print("✅ ファイル存在:", os.path.isfile(ssl_ca))

# デバッグ用ログ出力
print("Encoded DB_PASSWORD:", DB_PASSWORD)

# MySQLのURL構築(本番はこっち)
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?ssl_ca={SSL_CERT_PATH}"

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

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
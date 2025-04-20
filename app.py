from fastapi import FastAPI, HTTPException, Query, Request, File, UploadFile, Form, APIRouter, Body
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import json
from email_utils import generate_verification_code, send_verification_email
from db_control.connect_MySQL import SessionLocal
from db_control import crud, mymodels_MySQL
# from db_control.crud import insertTransaction
from dotenv import load_dotenv
import os
from sqlalchemy.orm import Session
from datetime import datetime,timedelta,date
from azure.storage.blob import BlobServiceClient
from azure.storage.blob import ContentSettings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv
import uuid
from typing import List, Optional



load_dotenv()

print("DEBUG SENDGRID_API_KEY (partial):", os.getenv("SENDGRID_API_KEY")[:10])
print("DEBUG FROM_EMAIL:", os.getenv("FROM_EMAIL"))

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")

app = FastAPI()

# ログイン用の認証（user_id 不要）
class LoginCodeVerifyRequest(BaseModel):
    email: str
    code: str

# ログイン───── ④ DBセッション関数（定型）─────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class LoginSendCodeRequest(BaseModel):
    email: str

@app.post("/auth/send-login-code")
def send_login_code(data: LoginSendCodeRequest, db: Session = Depends(get_db)):
    # 登録済みユーザーをDBから検索
    user = db.query(mymodels_MySQL.User).filter_by(email=data.email).first()

    if not user:
        print(f"🚫 未登録のメールアドレスが指定されました: {data.email}")
        raise HTTPException(status_code=404, detail="このメールアドレスは登録されていません")

    # 認証コードを生成
    code = generate_verification_code()
    expiry = datetime.now() + timedelta(minutes=5)

    # DBに保存
    user.verification_code = code
    user.code_expiry = expiry
    db.commit()

    # メール送信
    send_verification_email(data.email, code)
    print(f"✅ 認証コードを {data.email} に送信しました（code: {code}）")
    return {"message": "ログイン用の認証コードを送信しました"}

@app.post("/auth/login-verify-code")
def login_verify_code(data: LoginCodeVerifyRequest, db: Session = Depends(get_db)):
    user = db.query(mymodels_MySQL.User).filter_by(email=data.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    if user.verification_code != data.code:
        raise HTTPException(status_code=401, detail="認証コードが一致しません")
    if user.code_expiry < datetime.now():
        raise HTTPException(status_code=401, detail="認証コードの有効期限が切れています")

    return {"message": "ログイン成功", "user_id": user.user_id}


def send_verification_email(to_email: str, code: str) -> bool:
    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject='【FHSP】認証コードのお知らせ',
        plain_text_content=f'以下の認証コードを入力してください：\n\n{code}'
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(response.status_code)
        return response.status_code == 202
    except Exception as e:
        print(f"SendGrid送信失敗: {e}")
        return False

# テスト用APIエンドポイント
@app.get("/send-test-email")
def send_test_email(to: str = Query(..., description="テスト送信先メールアドレス")):
    code = "123456"  # テスト用の認証コード
    success = send_verification_email(to, code)
    if success:
        return {"message": "メール送信成功！"}
    else:
        return {"message": "メール送信失敗…"}

# MySQLのテーブル作成
from db_control.create_tables_MySQL import init_db

# # アプリケーション初期化時にテーブルを作成
init_db()

# app = FastAPI()
    
# Azure Blob Storageの接続設定
ACCOUNT_NAME = os.getenv('AZURE_STORAGE_ACCOUNT_NAME')
ACCOUNT_KEY = os.getenv('AZURE_STORAGE_ACCOUNT_KEY')
CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def index():
    return {"message": "FastAPI top page!!"}


# ログイン───── ⑤ send-codeエンドポイント─────
class SendCodeRequest(BaseModel):
    email: str
    user_id: int  # フロントから送られてくるuser_idに対応

@app.post("/auth/send-code")
def send_verification_code(data: SendCodeRequest, db: Session = Depends(get_db)):
    try:
        # ✅ user_idでユーザーを検索
        user = db.query(mymodels_MySQL.User).filter_by(user_id=data.user_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        
        # ✅ 認証コードを生成して保存
        code = generate_verification_code()
        expiry = datetime.now() + timedelta(minutes=5)

        user.verification_code = code
        user.code_expiry = expiry

        # ✅ このタイミングでメールアドレスを更新（Step1ではemail=None）
        user.email=data.email

        db.commit()

        send_verification_email(data.email, code)

        return {"message": "認証コードを送信しました（テストコード: " + code + ")"}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"送信失敗: {str(e)}")
    
# リクエスト用のデータモデル
class CodeVerifyRequest(BaseModel):
    email: str
    code: str

# DBセッション取得
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CodeVerifyRequest(BaseModel):
    user_id: int
    email: str
    code: str

@app.post("/auth/verify-code")
def verify_code(data: CodeVerifyRequest, db: Session = Depends(get_db)):
    print("💬 受け取ったリクエストボディ:", data)
    user = db.query(mymodels_MySQL.User).filter_by(email=data.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

    if user.verification_code != data.code:
        raise HTTPException(status_code=401, detail="認証コードが一致しません")

    if user.code_expiry < datetime.now():
        raise HTTPException(status_code=401, detail="認証コードの有効期限が切れています")
    
    # ✅ 認証成功 → メールアドレスを更新
    user.email = data.email
    db.commit()

    return {"message": "認証成功", "user_id": user.user_id}
    # ログイン成功とみなす（JWTやセッションは今後追加）
    # return {"message": "ログイン成功", "user_id": user.user_id}

# 新規登録Step1
class RegisterStep1Request(BaseModel):
    name: str
    name_kana: str
    gender: str  # 'M', 'F', 'U'
    birth_date: date  # フロントの入力は 'YYYY-MM-DD'
    postal_code: str
    address1: str
    address2: str
    email: str


@app.post("/register/step1")
def register_step1(data: RegisterStep1Request, db: Session = Depends(get_db)):
    try:
        user_id = crud.insert_user_step1(db, data)
        return {"message": "Step1 登録完了", "user_id": user_id}
    except Exception as e:
        print("Step1登録エラー:", e)
        raise HTTPException(status_code=500, detail="Step1登録に失敗しました")

    
# 新規登録Step2
class RegisterStep2Request(BaseModel):
    user_id: int
    tags: List[str]

from fastapi import Body

@app.post("/register/step2")
def register_step2(
    user_id: int = Body(...),
    tags: List[str] = Body(...)
):
    try:
        for tag_name in tags:
            tag_id = crud.getTagIdByName(tag_name)
            crud.insertUserTag(user_id=user_id, tag_id=tag_id)
        return {"message": "Step2（興味タグ）登録完了"}
    except Exception as e:
        print(f"Step2 登録エラー: {e}")
        raise HTTPException(status_code=500, detail="Step2 登録に失敗しました")

# 新規登録Step4 Pydanticモデル
class RegisterStep4Request(BaseModel):
    user_id: int
    nimoca_id: str
    saibugas_id: str

# Step4: nimoca ID と saibugas ID を登録
@app.post("/register/step4")
def register_step4(data: RegisterStep4Request, db: Session = Depends(get_db)):
    try:
        # user_id でユーザーを取得
        user = db.query(mymodels_MySQL.User).filter_by(user_id=data.user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")

        # nimoca_id と saibugas_id を更新
        user.nimoca_id = data.nimoca_id
        user.saibugas_id = data.saibugas_id

        db.commit()
        return {"message": "Step4 登録成功"}
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Step4 登録失敗: {str(e)}")


@app.get("/event")
def db_read(store_id: int = Query(...)):
    event_list = crud.selectEvent(store_id)
    print("Received event_list:")
    if not event_list:
        return {"message": "開催予定のイベントはありません"}
    return event_list

# ファイルをAzure Blob Storageに保存する関数
def save_file_to_blob(file: UploadFile) -> str:
    try:
        # BlobServiceClientの初期化
        blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
        
        # コンテナが存在するか確認し、存在しない場合は作成
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)
        try:
            container_client.get_container_properties()
            print(f"コンテナ '{CONTAINER_NAME}' は既に存在します。")
        except Exception as e:
            if 'ContainerNotFound' in str(e):
                print(f"コンテナ '{CONTAINER_NAME}' が見つかりません。作成します。")
                container_client.create_container()
                print(f"コンテナ '{CONTAINER_NAME}' を作成しました。")
            else:
                raise e
        
        # ユニークなファイル名を生成
        unique_filename = f"{uuid.uuid4()}_{file.filename}"

        # ファイルタイプに応じたContent-Typeを設定
        content_type = None
        filename_lower = file.filename.lower()
        if filename_lower.endswith('.jpg') or filename_lower.endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif filename_lower.endswith('.png'):
            content_type = 'image/png'
        elif filename_lower.endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename_lower.endswith('.gif'):
            content_type = 'image/gif'
        
        # BlobClientの取得
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=unique_filename)
        
        # ファイルポインタを先頭に戻す
        file.file.seek(0)
        
        # ファイルの内容を読み込む
        file_content = file.file.read()
        
        # Content-Typeを指定してBlobにアップロード
        blob_client.upload_blob(
            file_content, 
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type)
        )
        
        # アップロードされたファイルのURLを生成
        blob_url = f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}/{unique_filename}"
        
        print(f"ファイル '{file.filename}' をアップロードしました。URL: {blob_url}")
        return blob_url
    except Exception as e:
        print(f"Error uploading to Azure Blob Storage: {e}")
        raise e

@app.post("/event-register")
async def add_event(
    request: Request,
    eventName: str = Form(...),
    startDate: str = Form(...),
    endDate: str = Form(...),
    startTime: str = Form(...),
    endTime: str = Form(...),
    description: str = Form(...),
    information: Optional[str] = Form(None),
    store_id: int = Form(...),
    tags: List[str] = Form([]),
    flyer: Optional[UploadFile] = None,
    eventImage: Optional[UploadFile] = None
):
    form = await request.form()
    print("Received values:", form)

    for key, value in form.items():
        if isinstance(value, UploadFile):
            print(f"File in form: {key}, filename: {value.filename}, size: {value.size}")
    print("flyer param check:", flyer)
    print("eventImage param check:", eventImage)

    try:
        flyer_url = save_file_to_blob(flyer) if flyer else None
        event_image_url = save_file_to_blob(eventImage) if eventImage else None

        event_data = [{
            "event_name": eventName,
            "start_date": startDate,
            "end_date": endDate,
            "start_at": startTime,
            "end_at": endTime,
            "description": description,
            "information": information,
            "flyer_url": flyer_url,
            "event_image_url": event_image_url,
            "store_id": store_id
        }]
        print("event_data:", event_data)
        print("tags:", tags)

        event_id = crud.insertEvent(event_data)
        if tags:
            crud.insertEventTag(event_id, tags)

        return JSONResponse(
            status_code=200,
            content={
                "message": "イベント登録成功！", 
                "event_id": event_id, 
                "flyer_url": flyer_url,
                "event_image_url": event_image_url
            }
        )

    except Exception as e:
        print(f"エラー: {e}")
        raise HTTPException(status_code=500, detail=f"投稿に失敗しました: {str(e)}")


@app.get("/users/{user_id}")
def get_customer(user_id: str):
    user_info = crud.getuserById(user_id)
    if not user_info:
        raise HTTPException(status_code=404, detail="顧客が見つかりません")
    return user_info

class PointTransactionRequest(BaseModel):
    user_id: int
    store_id: int
    point: int
    type: str

@app.post("/points/transaction")
def record_transaction(data: PointTransactionRequest):
    print(data)
    try:
        crud.insertUserAndStoreTransaction(data)
        if data.type == "earn":
            return {"message": f"ユーザー：{data.user_id}に{data.point}ポイントを付与しました。"}
        elif data.type == "use":
            return {"message": f"ユーザー：{data.user_id}から{data.point}ポイントを減算しました。"}
    except Exception as e:
        print(f"エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tags")
def get_tags():
    return crud.get_all_tags()

# recommendation.py からルーターをインポート
from recommendation import router as recommendation_router

# アプリにルーターを登録
app.include_router(recommendation_router)

# ルートのパス設定を出力（デバッグ用）
print("Available routes:")
for route in app.routes:
    print(f"{route.path} [{', '.join(route.methods)}]")


class FavoriteEvent(BaseModel):
    user_id: int
    event_id: int
    event_title: str
    image_url: str
    area: str
    date: str

@app.post("/favorites/{user_id}/{event_id}")
def add_favorite(user_id: int, event_id: int):
    try:
        crud.insert_favorite_event(user_id, event_id)
        return {"message": "お気に入りに追加しました"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/favorites/{user_id:int}/{event_id:int}")
def remove_favorite(user_id: int, event_id: int):
    try:
        crud.delete_favorite_event(user_id, event_id)
        return {"message": "お気に入りを解除しました"}
    except Exception as e:
        print("お気に入り解除エラー:", e)
        raise HTTPException(status_code=500, detail="解除に失敗しました")

@app.get("/favorites/{user_id}")
def get_favorite_events(user_id: int):
    try:
        favorites = crud.get_favorite_events(user_id)
        return {"favorites": favorites}
    except Exception as e:
        print("お気に入り取得エラー:", e)
        raise HTTPException(status_code=500, detail="取得に失敗しました")

# イベント検索
@app.get("/events/search")
def search_events(keyword: str = '', date: str = '', tags: str = ''):
    try:
        result = crud.search_events(keyword, date, tags)
        return {"events": result}
    except Exception as e:
        print("イベント検索エラー:", e)
        raise HTTPException(status_code=500, detail="検索に失敗しました")

@app.get("/events/upcoming")
def get_upcoming_events():
    try:
        events = crud.get_upcoming_events()
        return {"events": events}
    except Exception as e:
        print(f"エラー: {e}")
        raise HTTPException(status_code=500, detail="イベント取得に失敗しました")
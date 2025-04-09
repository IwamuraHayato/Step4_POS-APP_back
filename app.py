from fastapi import FastAPI, HTTPException, Query, Request, File, UploadFile, Form, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import json
from db_control import crud, mymodels_MySQL
# from db_control.crud import insertTransaction
from dotenv import load_dotenv
import os
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.storage.blob import ContentSettings
from dotenv import load_dotenv
import uuid
from typing import List, Optional


load_dotenv()

# MySQLのテーブル作成
from db_control.create_tables_MySQL import init_db

# # アプリケーション初期化時にテーブルを作成
init_db()

app = FastAPI()
    
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
    information: str = Form(...),
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

@app.post("/favorites")
def add_favorite(event: FavoriteEvent):
    try:
        crud.insert_favorite_event(event)
        return {"message": "お気に入りに追加しました"}
    except Exception as e:
        print("お気に入り登録エラー:", e)
        raise HTTPException(status_code=500, detail="登録に失敗しました")

@app.delete("/favorites/{user_id:int}/{event_id:int}")
def remove_favorite(user_id: int, event_id: int):
    try:
        crud.delete_favorite_event(user_id, event_id)
        return {"message": "お気に入りを解除しました"}
    except Exception as e:
        print("お気に入り解除エラー:", e)
        raise HTTPException(status_code=500, detail="解除に失敗しました")

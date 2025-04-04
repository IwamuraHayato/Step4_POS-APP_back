from fastapi import FastAPI, HTTPException, Query, Request
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
from dotenv import load_dotenv

load_dotenv()

# MySQLのテーブル作成
from db_control.create_tables_MySQL import init_db

# # アプリケーション初期化時にテーブルを作成
init_db()

app = FastAPI()

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

@app.post("/event-register")
async def add_event(request: Request):
    form = await request.form()
    print("Received values:", form)
    try:
        event_data = [{
            "event_name": form["eventName"],
            "start_date": form["startDate"], 
            "end_date": form["endDate"],
            "start_at": form["startTime"],
            "end_at": form["endTime"],
            "description": form["description"],
            "information": form["information"],
            "store_id": int(form["store_id"])
        }]
        print("event_data:", event_data)
        event_tags = form.getlist("tags[]")
        print("tags:", event_tags)

        event_id = crud.insertEvent(event_data)
        crud.insertEventTag(event_id, event_tags)

        return {"message": "イベント登録成功！"}
    except Exception as e:
        print(f"エラー: {e}")
        return {"error": f"投稿に失敗しました: {str(e)}"}, 500
    
def save_images(files, post_id, session):
    # BlobServiceClientの初期化
    blob_service_client = BlobServiceClient(
        f"https://{ACCOUNT_NAME}.blob.core.windows.net",
        credential=ACCOUNT_KEY
    )
    """Images テーブルへのデータ挿入"""
    position = 1  # position を初期化
    for key in files:
        file = files[key]
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        try:
            # BlobClientの取得
            blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=unique_filename)
            
            # ファイルをBlob Storageにアップロード
            blob_client.upload_blob(file, overwrite=True)
            print(f"File uploaded to Azure Blob Storage: {unique_filename}")

            # Azure Blob StorageのURLを生成
            blob_url = f"https://{ACCOUNT_NAME}.blob.core.windows.net/{CONTAINER_NAME}/{unique_filename}"
            
            image_data = {
                "post_id": post_id,
                "image_url": blob_url,  # 相対パスを保存
                "position": position
            }
            session.execute(insert(mymodels.Images).values(image_data))
            # 次のファイルのために position をインクリメント
            position += 1
        except Exception as e:
            print(f"Error uploading to Azure Blob Storage: {e}")

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




# 以下POSAPP用のエンドポイント
@app.get("/api/read")
def db_read(itemCode: int = Query(...)):
    result = crud.myselect(mymodels_MySQL.Product, itemCode)
    if result is None:
        return {"message": "商品マスタ未登録です"}
    result_obj = json.loads(result)
    return result_obj[0] if result_obj else {"message": "商品マスタ未登録です"}

@app.post("/api/purchase")
async def add_db(request: Request):
    values = await request.json()
    values["timestamp"] = datetime.strptime(values["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d %H:%M:%S")
    transaction_data = [
        {
            "DATETIME": values["timestamp"],
            "EMP_CD": values["EMP_info"]["EMP_CD"],
            "STORE_CD": values["EMP_info"]["STORE_CD"],
            "POS_NO": values["EMP_info"]["POS_NO"],
            "TOTAL_AMT": 0,
            "TTL_AMT_EX_TAX": 0
        }]
    TOTAL_AMT = transaction_data[0]["TOTAL_AMT"]
    TTL_AMT_EX_TAX = transaction_data[0]["TTL_AMT_EX_TAX"]

    print("Received values:", values)
    print("transaction_data:", transaction_data)
    try:
        with crud.session_scope() as session:
            TRD_ID = crud.insertTransaction(transaction_data)
            for item in values["items"]:
                detail_data = {
                        "TRD_ID": TRD_ID,
                        "PRD_ID": item["PRD_ID"],
                        "PRD_CODE": item["CODE"],
                        "PRD_NAME": item["NAME"],
                        "PRD_PRICE": item["PRICE"],
                        "TAX_CD": 10
                        }
                PRD_PRICE_with_TAX =crud.insertDetails(detail_data)
                TOTAL_AMT += PRD_PRICE_with_TAX
                TTL_AMT_EX_TAX += detail_data["PRD_PRICE"]
            print(TRD_ID)
            print(TOTAL_AMT)
            print(TTL_AMT_EX_TAX)
            TTL_AMT = crud.insetTotalamt(TOTAL_AMT, TRD_ID, TTL_AMT_EX_TAX)
        return {f"購入金額(税込)：{TTL_AMT}"}, 201
    except Exception as e:
        print(f"エラー: {e}")
        return {"error": f"投稿に失敗しました: {str(e)}"}, 500




# @app.post("/customers")
# def create_customer(customer: Customer):
#     values = customer.dict()
#     tmp = crud.myinsert(mymodels.Customers, values)
#     result = crud.myselect(mymodels.Customers, values.get("customer_id"))

#     if result:
#         result_obj = json.loads(result)
#         return result_obj if result_obj else None
#     return None


# @app.get("/customers")
# def read_one_customer(customer_id: str = Query(...)):
#     result = crud.myselect(mymodels.Customers, customer_id)
#     if not result:
#         raise HTTPException(status_code=404, detail="Customer not found")
#     result_obj = json.loads(result)
#     return result_obj[0] if result_obj else None


# @app.get("/allcustomers")
# def read_all_customer():
#     result = crud.myselectAll(mymodels.Customers)
#     # 結果がNoneの場合は空配列を返す
#     if not result:
#         return []
#     # JSON文字列をPythonオブジェクトに変換
#     return json.loads(result)


# @app.put("/customers")
# def update_customer(customer: Customer):
#     values = customer.dict()
#     values_original = values.copy()
#     tmp = crud.myupdate(mymodels.Customers, values)
#     result = crud.myselect(mymodels.Customers, values_original.get("customer_id"))
#     if not result:
#         raise HTTPException(status_code=404, detail="Customer not found")
#     result_obj = json.loads(result)
#     return result_obj[0] if result_obj else None


# @app.delete("/customers")
# def delete_customer(customer_id: str = Query(...)):
#     result = crud.mydelete(mymodels.Customers, customer_id)
#     if not result:
#         raise HTTPException(status_code=404, detail="Customer not found")
#     return {"customer_id": customer_id, "status": "deleted"}


# @app.get("/fetchtest")
# def fetchtest():
#     response = requests.get('https://jsonplaceholder.typicode.com/users')
#     return response.json()

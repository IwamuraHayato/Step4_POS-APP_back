from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json
from db_control import crud, mymodels_MySQL
from db_control.crud import insertTransaction
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

# MySQLのテーブル作成
from db_control.create_tables_MySQL import init_db

# # アプリケーション初期化時にテーブルを作成
init_db()


class Customer(BaseModel):
    customer_id: str
    customer_name: str
    age: int
    gender: str

app = FastAPI()

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/read")
def db_read(itemCode: int = Query(...)):
    result = crud.myselect(mymodels_MySQL.Product, itemCode)
    if not result:
        raise HTTPException(status_code=404, detail="商品マスタ未登録です")
    result_obj = json.loads(result)
    return result_obj[0] if result_obj else None

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
            "TOTAL_AMT": 0
        }]
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
                        "PRD_PRICE": item["PRICE"]
                        }
                TOTAL_AMT =crud.insertDetails(detail_data)
            print(TOTAL_AMT)
            print(TRD_ID)
            crud.insetTotalamt(TOTAL_AMT, TRD_ID)
        return {f"購入金額：{TOTAL_AMT}"}, 201
    except Exception as e:
        print(f"エラー: {e}")
        return {"error": f"投稿に失敗しました: {str(e)}"}, 500


@app.get("/")
def index():
    return {"message": "FastAPI top page!!"}


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

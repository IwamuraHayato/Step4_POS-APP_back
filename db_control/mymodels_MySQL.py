from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, DECIMAL
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class Product(Base):
    __tablename__ = 'm_product_iwamu'

    PRD_ID = Column(Integer, primary_key=True, autoincrement=True)  # Product ID
    CODE = Column(String(13), unique=True, nullable=False)  # Product Code (Unique)
    NAME = Column(String(50), nullable=False)  # Product Name
    PRICE = Column(Integer, nullable=False)  # Product Price

    def __repr__(self):
        return f"<Product(PRD_ID={self.PRD_ID}, NAME={self.NAME}, PRICE={self.PRICE})>"


class Transaction(Base):
    __tablename__ = 'transactions_iwamu'

    TRD_ID = Column(Integer, primary_key=True, autoincrement=True)  # Transaction ID
    DATETIME = Column(DateTime, default=datetime.utcnow, nullable=False)  # Transaction DateTime
    EMP_CD = Column(String(10), nullable=True)  # Employee Code
    STORE_CD = Column(String(5), nullable=True)  # Store Code
    POS_NO = Column(String(3), nullable=True)  # POS Machine ID
    TOTAL_AMT = Column(Integer, nullable=False)  # Total Amount
    TTL_AMT_EX_TAX = Column(Integer, nullable=True)  # Total AmountEX_TAX
    details = relationship("TransactionDetail", back_populates="transaction", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Transaction(TRD_ID={self.TRD_ID}, DATETIME={self.DATETIME})>"


class TransactionDetail(Base):
    __tablename__ = 'transaction_details_iwamu'

    DTL_ID = Column(Integer, primary_key=True, autoincrement=True)  # Detail ID
    TRD_ID = Column(Integer, ForeignKey('transactions_iwamu.TRD_ID', ondelete="CASCADE"), nullable=False)  # Transaction ID (Foreign Key)
    PRD_ID = Column(Integer, ForeignKey('m_product_iwamu.PRD_ID', ondelete="CASCADE"), nullable=False)  # Product ID (Foreign Key)
    PRD_CODE = Column(String(13), nullable=False)  # Product Code
    PRD_NAME = Column(String(50), nullable=False)  # Product Name
    PRD_PRICE = Column(Integer, nullable=False)  # Product Price
    TAX_CD =  Column(String(2), nullable=False)
    transaction = relationship("Transaction", back_populates="details")
    product = relationship("Product")

    def __repr__(self):
        return f"<TransactionDetail(DTL_ID={self.DTL_ID}, PRD_NAME={self.PRD_NAME}, PRD_PRICE={self.PRD_PRICE})>"


class Tax(Base):
    __tablename__ = 'tax_master_iwamu'

    ID = Column(Integer, primary_key=True, autoincrement=True)
    TAX_CD = Column(String(2), unique=True, nullable=False)
    TAX_NAME = Column(String(20), nullable=False)
    PERCENT = Column(DECIMAL(5,2), nullable=False)

    def __repr__(self):
        return f"<TaxMaster(ID={self.ID}, CODE={self.CODE}, NAME={self.NAME}, PERCENT={self.PERCENT})>"

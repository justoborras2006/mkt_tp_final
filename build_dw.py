import os
import pandas as pd

RAW = "raw"
DW = "DW"
os.makedirs(DW, exist_ok=True)

def yyyymmdd(s): return s.dt.strftime("%Y%m%d").astype("Int64")
def hhmmss(s):  return s.dt.strftime("%H:%M:%S")

channel  = pd.read_csv(f"{RAW}/channel.csv")
customer = pd.read_csv(f"{RAW}/customer.csv")
address  = pd.read_csv(f"{RAW}/address.csv")
province = pd.read_csv(f"{RAW}/province.csv")
product  = pd.read_csv(f"{RAW}/product.csv")
p_cat    = pd.read_csv(f"{RAW}/product_category.csv")
store    = pd.read_csv(f"{RAW}/store.csv")
so       = pd.read_csv(f"{RAW}/sales_order.csv", parse_dates=["order_date"])
soi      = pd.read_csv(f"{RAW}/sales_order_item.csv")
payment  = pd.read_csv(f"{RAW}/payment.csv", parse_dates=["paid_at"], dtype={"order_id":"Int64"})
shipment = pd.read_csv(f"{RAW}/shipment.csv", parse_dates=["shipped_at","delivered_at"], dtype={"order_id":"Int64"})
web      = pd.read_csv(f"{RAW}/web_session.csv", parse_dates=["started_at","ended_at"])
nps      = pd.read_csv(f"{RAW}/nps_response.csv", parse_dates=["responded_at"])

dim_channel = channel.rename(columns={"code":"channel_code","name":"channel_name"})[["channel_id","channel_code","channel_name"]]
dim_channel.to_csv(f"{DW}/dim_channel.csv", index=False)

dim_customer = customer.rename(columns={"first_name":"cust_first_name","last_name":"cust_last_name"})
cols_cust = [c for c in ["customer_id","email","cust_first_name","cust_last_name","phone","status","created_at"] if c in dim_customer.columns]
dim_customer = dim_customer[cols_cust]
dim_customer.to_csv(f"{DW}/dim_customer.csv", index=False)

dim_address = address.merge(province.rename(columns={"name":"name","code":"code"})[["province_id","name","code"]], on="province_id", how="left")
cols_addr = [c for c in ["address_id","line1","line2","city","province_id","postal_code","country_code","created_at","name","code"] if c in dim_address.columns]
dim_address = dim_address[cols_addr]
dim_address.to_csv(f"{DW}/dim_address.csv", index=False)

dim_product = product.rename(columns={"name":"product_name"}).merge(p_cat.rename(columns={"name":"category_name"}), on="category_id", how="left")
cols_prod = [c for c in ["product_id","sku","product_name","category_id","list_price","status","created_at","category_name"] if c in dim_product.columns]
dim_product = dim_product[cols_prod]
dim_product.to_csv(f"{DW}/dim_product.csv", index=False)

dim_store = store.copy()
dim_store.to_csv(f"{DW}/dim_store.csv", index=False)

dates = pd.concat([
    so["order_date"], payment["paid_at"], shipment["shipped_at"], shipment["delivered_at"],
    web["started_at"], web["ended_at"], nps["responded_at"]
], ignore_index=True).dropna().dt.normalize().drop_duplicates().sort_values()
dim_calendar = pd.DataFrame({"date": dates})
dim_calendar["date_id"] = yyyymmdd(dim_calendar["date"])
dim_calendar["year"] = dim_calendar["date"].dt.year
dim_calendar["quarter"] = dim_calendar["date"].dt.quarter
dim_calendar["month"] = dim_calendar["date"].dt.month
dim_calendar["day"] = dim_calendar["date"].dt.day
dim_calendar["week"] = dim_calendar["date"].dt.isocalendar().week.astype(int)
dim_calendar.to_csv(f"{DW}/dim_calendar.csv", index=False)

fact_sales_order = so.merge(dim_channel, on="channel_id", how="left")
if "order_date" in fact_sales_order.columns:
    fact_sales_order["order_date_id"] = yyyymmdd(pd.to_datetime(fact_sales_order["order_date"]))
cols_fso = [c for c in [
    "order_id","customer_id","channel_id","store_id","order_date","order_date_id",
    "billing_address_id","shipping_address_id","status","currency_code",
    "subtotal","tax_amount","shipping_cost","channel_code","channel_name"
] if c in fact_sales_order.columns]
fact_sales_order = fact_sales_order[cols_fso]
fact_sales_order.to_csv(f"{DW}/fact_sales_order.csv", index=False)

soi_enriched = soi.merge(so[["order_id","order_date"]], on="order_id", how="left")
soi_enriched["month"] = pd.to_datetime(soi_enriched["order_date"]).dt.to_period("M").astype(str)
fact_sales_order_item = soi_enriched.merge(dim_product[["product_id","product_name","category_id","category_name"]], on="product_id", how="left")
cols_soi = [c for c in [
    "order_item_id","order_id","product_id","quantity","unit_price","discount_amount",
    "line_total","order_date","product_name","category_id","category_name","month"
] if c in fact_sales_order_item.columns]
fact_sales_order_item = fact_sales_order_item[cols_soi]
fact_sales_order_item.to_csv(f"{DW}/fact_sales_order_item.csv", index=False)

fact_payment = payment.copy()
cols_pay = [c for c in ["payment_id","order_id","method","status","amount","paid_at","transaction_ref"] if c in fact_payment.columns]
fact_payment = fact_payment[cols_pay]
fact_payment.to_csv(f"{DW}/fact_payment.csv", index=False)

fact_shipment = shipment.copy()
cols_ship = [c for c in ["shipment_id","order_id","carrier","tracking_number","status","shipped_at","delivered_at"] if c in fact_shipment.columns]
fact_shipment = fact_shipment[cols_ship]
fact_shipment.to_csv(f"{DW}/fact_shipment.csv", index=False)

fact_web_session = pd.DataFrame({
    "id": web.get("id", web.get("session_id")),
    "customer_id": web["customer_id"],
    "started_at_date_id": yyyymmdd(web["started_at"]),
    "started_at_time": hhmmss(web["started_at"]),
    "ended_at_date_id": yyyymmdd(web["ended_at"]),
    "ended_at_time": hhmmss(web["ended_at"]),
    "source": web["source"],
    "device": web["device"]
})
fact_web_session = fact_web_session[["id","customer_id","started_at_date_id","started_at_time","ended_at_date_id","ended_at_time","source","device"]]
fact_web_session.to_csv(f"{DW}/fact_web_session.csv", index=False)

fact_nps_response = nps.merge(dim_channel, on="channel_id", how="left")
cols_nps = [c for c in [
    "nps_id","customer_id","channel_id","score","responded_at","comment","channel_code","channel_name"
] if c in fact_nps_response.columns]
if cols_nps:
    fact_nps_response = fact_nps_response[cols_nps]
fact_nps_response.to_csv(f"{DW}/fact_nps_response.csv", index=False)

print("OK")

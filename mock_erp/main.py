"""Mock ERP：模拟企业 ERP 后端，提供采购相关的 HTTP 接口（测试替身）。

用于本地开发调试，提供与真实 ERP 一致的数据结构与接口：
供应商 / 物料 / 库存 / 采购订单。接入真实 ERP 时，
只需把 ERP_BASE_URL 指向真实服务地址即可，无需改动调用方。

运行：python -m mock_erp.main
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Mock ERP", version="0.1.0")

# ===== 模拟数据 =====
SUPPLIERS: dict[str, dict] = {
    "S001": {"id": "S001", "name": "华东钢铁集团", "category": "钢材", "rating": 4.8,
             "contact": "王经理", "phone": "021-88880001", "email": "sales@hdsteel.com"},
    "S002": {"id": "S002", "name": "精密轴承有限公司", "category": "机械", "rating": 4.5,
             "contact": "李经理", "phone": "0512-66660002", "email": "li@bearing.cn"},
    "S003": {"id": "S003", "name": "华南电子元件厂", "category": "电子", "rating": 4.2,
             "contact": "张经理", "phone": "0755-33330003", "email": "zhang@hndz.com"},
    "S004": {"id": "S004", "name": "北方化工原料有限公司", "category": "化工", "rating": 4.0,
             "contact": "赵经理", "phone": "022-22220004", "email": "zhao@chem.com"},
    "S005": {"id": "S005", "name": "中西部五金制品厂", "category": "五金", "rating": 4.6,
             "contact": "孙经理", "phone": "029-11110005", "email": "sun@wujin.cn"},
}

PARTS: dict[str, dict] = {
    "P001": {"id": "P001", "name": "冷轧钢板", "category": "钢材", "unit": "吨", "price": 4200.0, "supplier_id": "S001"},
    "P002": {"id": "P002", "name": "不锈钢螺丝 M6", "category": "五金", "unit": "盒", "price": 35.5, "supplier_id": "S005"},
    "P003": {"id": "P003", "name": "深沟球轴承 6204", "category": "机械", "unit": "个", "price": 18.8, "supplier_id": "S002"},
    "P004": {"id": "P004", "name": "电解电容 100uF", "category": "电子", "unit": "个", "price": 0.45, "supplier_id": "S003"},
    "P005": {"id": "P005", "name": "工业润滑油", "category": "化工", "unit": "桶", "price": 860.0, "supplier_id": "S004"},
    "P006": {"id": "P006", "name": "铝合金型材", "category": "钢材", "unit": "米", "price": 28.0, "supplier_id": "S001"},
    "P007": {"id": "P007", "name": "接线端子", "category": "电子", "unit": "个", "price": 0.12, "supplier_id": "S003"},
    "P008": {"id": "P008", "name": "齿轮减速机", "category": "机械", "unit": "台", "price": 1250.0, "supplier_id": "S002"},
}

INVENTORY: dict[str, dict] = {
    "P001": {"quantity": 120, "warning_threshold": 50},
    "P002": {"quantity": 30, "warning_threshold": 100},
    "P003": {"quantity": 8, "warning_threshold": 20},
    "P004": {"quantity": 5000, "warning_threshold": 1000},
    "P005": {"quantity": 45, "warning_threshold": 40},
    "P006": {"quantity": 200, "warning_threshold": 80},
    "P007": {"quantity": 900, "warning_threshold": 2000},
    "P008": {"quantity": 15, "warning_threshold": 10},
}

# 采购订单：用自增 id
_ORDER_SEQ = 0
ORDERS: dict[str, dict] = {}

# 供应商自增编号（已有 S001~S005，新供应商从 S006 开始）
_SUPPLIER_SEQ = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===== 请求模型 =====
class OrderCreate(BaseModel):
    part_id: str
    quantity: int
    unit_price: float | None = None  # 不传则用物料默认价
    order_type: str = "purchase"  # purchase=采购入库(+库存)；sale=销售出库(-库存)
    supplier_id: str | None = None  # 不传则用物料的默认供应商


class OrderUpdate(BaseModel):
    quantity: int | None = None
    unit_price: float | None = None
    status: str | None = None


class SupplierCreate(BaseModel):
    name: str
    category: str | None = None
    rating: float | None = None
    contact: str | None = None
    phone: str | None = None
    email: str | None = None


# ===== 辅助函数 =====
def _part_with_supplier(part_id: str) -> dict:
    part = PARTS.get(part_id)
    if part is None:
        raise HTTPException(status_code=404, detail=f"物料 {part_id} 不存在")
    supplier = SUPPLIERS.get(part["supplier_id"], {})
    return {**part, "supplier_name": supplier.get("name", "")}


# ===== 接口 =====
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/suppliers/{supplier_id}")
def supplier_query(supplier_id: str) -> dict:
    supplier = SUPPLIERS.get(supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"供应商 {supplier_id} 不存在")
    return supplier


@app.get("/api/suppliers")
def supplier_search(name: str = "") -> list[dict]:
    if not name:
        return list(SUPPLIERS.values())
    return [s for s in SUPPLIERS.values() if name in s["name"]]


@app.post("/api/suppliers")
def supplier_create(req: SupplierCreate) -> dict:
    global _SUPPLIER_SEQ
    _SUPPLIER_SEQ += 1
    supplier_id = f"S{_SUPPLIER_SEQ:03d}"
    supplier = {
        "id": supplier_id,
        "name": req.name,
        "category": req.category or "",
        "rating": req.rating or 0.0,
        "contact": req.contact or "",
        "phone": req.phone or "",
        "email": req.email or "",
    }
    SUPPLIERS[supplier_id] = supplier
    return supplier


@app.get("/api/parts/search")
def part_search(keyword: str = "") -> list[dict]:
    if not keyword:
        return [_part_with_supplier(p["id"]) for p in PARTS.values()]
    return [
        _part_with_supplier(p["id"])
        for p in PARTS.values()
        if keyword in p["name"] or keyword in p["category"]
    ]


@app.get("/api/parts/{part_id}")
def part_query(part_id: str) -> dict:
    return _part_with_supplier(part_id)


@app.get("/api/parts/by-supplier/{supplier_id}")
def part_by_supplier(supplier_id: str) -> list[dict]:
    return [
        _part_with_supplier(p["id"])
        for p in PARTS.values()
        if p["supplier_id"] == supplier_id
    ]


@app.post("/api/orders")
def order_create(req: OrderCreate) -> dict:
    global _ORDER_SEQ
    part = PARTS.get(req.part_id)
    if part is None:
        raise HTTPException(status_code=404, detail=f"物料 {req.part_id} 不存在")
    supplier_id = req.supplier_id or part["supplier_id"]
    supplier = SUPPLIERS.get(supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail=f"供应商 {supplier_id} 不存在")
    _ORDER_SEQ += 1
    order_id = f"O{_ORDER_SEQ:04d}"
    order = {
        "id": order_id,
        "part_id": req.part_id,
        "part_name": part["name"],
        "supplier_id": supplier_id,
        "supplier_name": supplier["name"],
        "quantity": req.quantity,
        "unit_price": req.unit_price if req.unit_price is not None else part["price"],
        "type": req.order_type,
        "status": "pending",
        "created_at": _now(),
        "updated_at": _now(),
    }
    ORDERS[order_id] = order
    return order


@app.put("/api/orders/{order_id}")
def order_update(order_id: str, req: OrderUpdate) -> dict:
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
    if req.quantity is not None:
        order["quantity"] = req.quantity
    if req.unit_price is not None:
        order["unit_price"] = req.unit_price
    if req.status is not None:
        order["status"] = req.status
    order["updated_at"] = _now()
    return order


@app.get("/api/orders/{order_id}")
def order_search_details(order_id: str) -> dict:
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
    return order


@app.get("/api/inventory")
def inventory_list() -> list[dict]:
    result = []
    for part_id, inv in INVENTORY.items():
        part = _part_with_supplier(part_id)
        result.append({
            "part_id": part_id,
            "part_name": part["name"],
            "unit": part["unit"],
            "quantity": inv["quantity"],
            "warning_threshold": inv["warning_threshold"],
            "low_stock": inv["quantity"] < inv["warning_threshold"],
        })
    return result


@app.get("/api/inventory/warning")
def inventory_warning() -> list[dict]:
    result = []
    for part_id, inv in INVENTORY.items():
        if inv["quantity"] < inv["warning_threshold"]:
            part = _part_with_supplier(part_id)
            result.append({
                "part_id": part_id,
                "part_name": part["name"],
                "quantity": inv["quantity"],
                "warning_threshold": inv["warning_threshold"],
                "supplier_id": part["supplier_id"],
                "supplier_name": part["supplier_name"],
            })
    return result


@app.get("/api/inventory/{part_id}")
def inventory_query(part_id: str) -> dict:
    inv = INVENTORY.get(part_id)
    if inv is None:
        raise HTTPException(status_code=404, detail=f"物料 {part_id} 无库存记录")
    part = _part_with_supplier(part_id)
    return {
        "part_id": part_id,
        "part_name": part["name"],
        "quantity": inv["quantity"],
        "warning_threshold": inv["warning_threshold"],
        "low_stock": inv["quantity"] < inv["warning_threshold"],
    }


@app.get("/api/orders")
def order_list() -> list[dict]:
    return list(ORDERS.values())


@app.post("/api/orders/{order_id}/place")
def order_place(order_id: str) -> dict:
    order = ORDERS.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"订单 {order_id} 不存在")
    if order["status"] == "placed":
        return order
    part_id = order["part_id"]
    inv = INVENTORY.get(part_id)
    if inv is None:
        raise HTTPException(status_code=500, detail=f"物料 {part_id} 无库存记录")
    quantity = order["quantity"]
    if order["type"] == "sale":
        # 销售出库：先检查库存，再扣减
        if inv["quantity"] < quantity:
            raise HTTPException(
                status_code=400,
                detail=f"库存不足：{part_id} 当前库存 {inv['quantity']}，销售 {quantity}",
            )
        inv["quantity"] -= quantity
    else:
        # 采购入库：库存增加
        inv["quantity"] += quantity
    order["status"] = "placed"
    order["updated_at"] = _now()
    return order


@app.get("/")
def index() -> FileResponse:
    """内置网页：浏览器打开 http://localhost:8080 查看库存/订单并操作下单。"""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)

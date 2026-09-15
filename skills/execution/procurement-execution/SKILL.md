---
name: procurement-execution
description: 采购执行员工作手册。当用户需要查询/生成/修改采购订单、直接下单，或查询物料、供应商、库存与预警时使用。
---

# 采购执行员工作手册

## 适用场景
- 生成采购/销售订单、修改订单、执行下单（采购入库=库存增加，销售出库=库存减少）。
- 查询物料、供应商、库存与预警、订单详情。

## 写操作流程（下单 / 改单）
1. 如果缺少必填字段（物料编号 `part_id`、数量 `quantity`），先调用 `request_order_info` 向用户补齐，不要在回复里直接问。
2. 信息齐全后：新建用 `order_create`（默认采购单，传 `order_type="sale"` 可建销售单），
   修改用 `order_update`，执行下单用 `order_place`（采购单=入库、库存增加；销售单=出库、库存减少）。
3. 这些写操作（`order_create` / `order_update` / `order_place`）执行前需要人工批准，调用后耐心等待批准结果，不要擅自重试或绕过。

## 向新供应商下单（调研到的新供应商）
1. 如果用户要下单给 ERP 里还没有的供应商（例如研究员网上调研到的新供应商），
   先调用 `supplier_create`（至少传 `name`），它会返回新供应商编号（如 S006）。
2. 再把返回的编号作为 `supplier_id` 传给 `order_create`，订单就会挂到新供应商名下。
3. 不要自己编造供应商编号，一切以 `supplier_create` 返回的编号为准。

## 读操作速查
- 查物料：`part_query`（单个）、`part_search`（关键字）、`part_by_supplier`（按供应商）
- 查供应商：`supplier_query`（单个）、`supplier_create`（新增）
- 查库存：`inventory_query`（单个）、`inventory_warning`（预警清单）
- 查订单：`order_list`（全部）、`order_search_details`（单个）

## 诚实原则（重要）
- 一切以工具返回为准，不要编造订单号、库存数量、物料或供应商信息。
- 若工具返回「不存在 / 库存不足」等错误，如实转达给用户，不要臆造一个成功结果。

"""MongoDB 实现的 LangGraph BaseStore（持久记忆存储）。

LangGraph 的 store 接口核心只有两个方法：batch / abatch，内部按操作类型分派：
GetOp 读一条、PutOp 写/删一条、SearchOp 按命名空间前缀查一批、ListNamespacesOp 列命名空间。

本实现用 pymongo（同步）落库；异步 abatch 用 asyncio.to_thread 丢到线程池执行，
避免阻塞事件循环。本项目是单用户、小数据量场景，这样最简单也最不容易出错。
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime, timezone

import pymongo
from langgraph.store.base import (
    BaseStore,
    GetOp,
    Item,
    ListNamespacesOp,
    MatchCondition,
    Op,
    PutOp,
    Result,
    SearchItem,
    SearchOp,
)


class MongoStore(BaseStore):
    def __init__(
        self,
        uri: str,
        db_name: str,
        collection_name: str = "langgraph_store",
    ) -> None:
        self._client = pymongo.MongoClient(uri)
        self._collection = self._client[db_name][collection_name]
        # 每条记录用 (namespace, key) 唯一标识
        self._collection.create_index([("namespace", 1), ("key", 1)], unique=True)

    # ---------- 对外核心：实现 BaseStore 的抽象方法 ----------
    def batch(self, ops: Iterable[Op]) -> list[Result]:
        results: list[Result] = []
        for op in ops:
            if isinstance(op, GetOp):
                results.append(self._get(op.namespace, op.key))
            elif isinstance(op, PutOp):
                self._put(op.namespace, op.key, op.value)
                results.append(None)
            elif isinstance(op, SearchOp):
                results.append(self._search(op))
            elif isinstance(op, ListNamespacesOp):
                results.append(self._list_namespaces(op))
            else:
                raise ValueError(f"未知操作类型: {type(op)}")
        return results

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        return await asyncio.to_thread(self.batch, ops)

    # ---------- 四种操作的具体实现 ----------
    def _get(self, namespace: tuple[str, ...], key: str) -> Item | None:
        doc = self._collection.find_one({"namespace": list(namespace), "key": key})
        return None if doc is None else self._doc_to_item(doc)

    def _put(self, namespace: tuple[str, ...], key: str, value: dict | None) -> None:
        ns = list(namespace)
        if value is None:
            self._collection.delete_one({"namespace": ns, "key": key})
            return
        now = datetime.now(timezone.utc)
        self._collection.update_one(
            {"namespace": ns, "key": key},
            {
                "$set": {"value": value, "updated_at": now},
                "$setOnInsert": {"namespace": ns, "key": key, "created_at": now},
            },
            upsert=True,
        )

    def _search(self, op: SearchOp) -> list[SearchItem]:
        query = self._namespace_prefix_query(op.namespace_prefix)
        if op.filter:
            query["value"] = self._translate_filter(op.filter)
        docs = (
            self._collection.find(query)
            .sort("key", pymongo.ASCENDING)
            .skip(op.offset)
            .limit(op.limit)
        )
        return [self._doc_to_search_item(doc) for doc in docs]

    def _list_namespaces(self, op: ListNamespacesOp) -> list[tuple[str, ...]]:
        docs = self._collection.find({}, {"namespace": 1})
        namespaces = sorted({tuple(d["namespace"]) for d in docs})
        if op.match_conditions:
            namespaces = [
                ns
                for ns in namespaces
                if all(self._does_match(c, ns) for c in op.match_conditions)
            ]
        if op.max_depth is not None:
            namespaces = sorted({ns[: op.max_depth] for ns in namespaces})
        return namespaces[op.offset : op.offset + op.limit]

    # ---------- 工具函数 ----------
    @staticmethod
    def _namespace_prefix_query(prefix: tuple[str, ...]) -> dict:
        # 命名空间存成数组，前缀匹配 = 数组前 N 个元素相等
        return {f"namespace.{i}": part for i, part in enumerate(prefix)}

    @staticmethod
    def _translate_filter(filter_dict: dict) -> dict:
        # LangGraph 的 filter 键就是 value 的字段名，$gt 等操作符和 MongoDB 同名
        return {f"value.{key}": cond for key, cond in filter_dict.items()}

    @staticmethod
    def _does_match(condition: MatchCondition, key: tuple[str, ...]) -> bool:
        path = condition.path
        if len(key) < len(path):
            return False
        if condition.match_type == "prefix":
            pairs = zip(key, path)
        else:  # suffix
            pairs = zip(reversed(key), reversed(path))
        return all(p == "*" or k == p for k, p in pairs)

    @staticmethod
    def _doc_to_item(doc) -> Item:
        return Item(
            value=doc["value"],
            key=doc["key"],
            namespace=tuple(doc["namespace"]),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    @classmethod
    def _doc_to_search_item(cls, doc) -> SearchItem:
        item = cls._doc_to_item(doc)
        return SearchItem(
            namespace=item.namespace,
            key=item.key,
            value=item.value,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

import { useCallback, useEffect, useState } from "react";

import { api } from "../lib/api";
import { streamTurn } from "../lib/sse";
import type { Banner, Health, LedgerEvent, Person, PersonListItem } from "../lib/types";

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  text: string;
  streaming?: boolean;
}

let _mid = 0;
const nextId = () => `m${++_mid}`;

/** 全应用状态机: 联系人 / 焦点真相(可时光机) / 账本 / 对话 / 待确认闸门。
 *  组件保持纯展示, 所有副作用与协调收口在这里。 */
export function useCrm() {
  const [health, setHealth] = useState<Health | null>(null);
  const [people, setPeople] = useState<PersonListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [person, setPerson] = useState<Person | null>(null);
  const [ledger, setLedger] = useState<LedgerEvent[]>([]);
  const [asOf, setAsOf] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [banners, setBanners] = useState<Banner[]>([]);
  const [streaming, setStreaming] = useState(false);

  const refreshPerson = useCallback(
    (id: number, at: string | null) => api.person(id, at).then(setPerson).catch(() => {}),
    [],
  );
  const refreshLedger = useCallback(
    (id: number) => api.ledger(id).then(setLedger).catch(() => {}),
    [],
  );
  const refreshPeople = useCallback(() => api.people().then(setPeople).catch(() => {}), []);

  // 首屏: health + 联系人, 选中第一个
  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
    api
      .people()
      .then((p) => {
        setPeople(p);
        if (p.length) setSelectedId((cur) => cur ?? p[0].id);
      })
      .catch(() => {});
  }, []);

  // 切联系人: 回到"现在", 清闸门, 拉真相 + 账本
  useEffect(() => {
    if (selectedId == null) return;
    setAsOf(null);
    setBanners([]);
    setMessages([]);
    void refreshPerson(selectedId, null);
    void refreshLedger(selectedId);
  }, [selectedId, refreshPerson, refreshLedger]);

  // 时光机: 把焦点真相拉到某时点 (null = 现在)
  const travelTo = useCallback(
    (at: string | null) => {
      setAsOf(at);
      if (selectedId != null) void refreshPerson(selectedId, at);
    },
    [selectedId, refreshPerson],
  );

  // 对话一轮: 流式回复 + 终态(闸门/真相/账本)
  const sendTurn = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (selectedId == null || streaming || !trimmed) return;
      const aid = nextId();
      setMessages((m) => [
        ...m,
        { id: nextId(), role: "user", text: trimmed },
        { id: aid, role: "agent", text: "", streaming: true },
      ]);
      setStreaming(true);
      setAsOf(null); // 跳回现在, 好让本轮写入可见

      try {
        await streamTurn(trimmed, selectedId, {
          onDelta: (t) =>
            setMessages((m) =>
              m.map((msg) => (msg.id === aid ? { ...msg, text: msg.text + t } : msg)),
            ),
          onDone: (d) => {
            setMessages((m) =>
              m.map((msg) => (msg.id === aid ? { ...msg, streaming: false } : msg)),
            );
            if (d.banners.length) setBanners((b) => [...b, ...d.banners]);
            if (d.person) setPerson(d.person);
            setLedger(d.ledger);
            void refreshPeople();
          },
        });
      } catch {
        setMessages((m) =>
          m.map((msg) =>
            msg.id === aid
              ? { ...msg, streaming: false, text: msg.text || "(请求失败，请稍后重试)" }
              : msg,
          ),
        );
      } finally {
        setStreaming(false);
      }
    },
    [selectedId, streaming, refreshPeople],
  );

  // 确认闸门: 采纳 / 驳回 → 刷新真相 + 账本 + 列表
  const resolveBanner = useCallback(
    async (intentId: number, action: "confirm" | "reject") => {
      if (selectedId == null) return;
      try {
        if (action === "confirm") await api.confirm([intentId]);
        else await api.reject([intentId]);
      } finally {
        setBanners((b) => b.filter((x) => x.intent_id !== intentId));
        setAsOf(null);
        void refreshPerson(selectedId, null);
        void refreshLedger(selectedId);
        void refreshPeople();
      }
    },
    [selectedId, refreshPerson, refreshLedger, refreshPeople],
  );

  return {
    health,
    people,
    selectedId,
    setSelectedId,
    person,
    ledger,
    asOf,
    travelTo,
    messages,
    banners,
    streaming,
    sendTurn,
    resolveBanner,
  };
}

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "../lib/api";
import { streamTurn } from "../lib/sse";
import type {
  Banner,
  Conversation,
  ConvMessage,
  Health,
  LedgerEvent,
  Person,
  PersonInput,
  PersonListItem,
  ToolEvent,
} from "../lib/types";

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  text: string;
  tools?: ToolEvent[];
  reasoning?: string;
  streaming?: boolean;
}

let _mid = 0;
const nextId = () => `m${++_mid}`;

const serverToChat = (m: ConvMessage): ChatMessage => ({
  id: `s${m.id}`,
  role: m.role,
  text: m.content,
  tools: m.tools ?? [],
  reasoning: m.reasoning ?? "",
});

function upsertTool(tools: ToolEvent[] | undefined, ev: ToolEvent): ToolEvent[] {
  const cur = tools ?? [];
  return cur.some((t) => t.id === ev.id)
    ? cur.map((t) => (t.id === ev.id ? { ...t, ...ev } : t))
    : [...cur, ev];
}

// 待确认闸门 = 焦点联系人账本里所有"还 PROPOSED 的 PATCH"。由账本派生(单一真源),
// 而非临时累积 —— 这样刷新/切换后仍可达, 不会出现"提了改动却永远没法确认"。
const pendingBanners = (ledger: LedgerEvent[]): Banner[] =>
  ledger
    .filter((e) => e.status === "PROPOSED" && e.kind === "PATCH")
    .map((e) => ({
      intent_id: e.id,
      target_field: e.target_field,
      proposed_value: e.target_field ? (e.patch_json[e.target_field] ?? null) : null,
      confidence: e.confidence,
    }));

/** 全应用状态机: 对话线程 / 联系人 / 焦点真相(可时光机) / 账本 / 待确认闸门。
 *  两个正交轴: activeConvId = 当前聊哪个线程; selectedId = 焦点联系人(驱动真相面板 +
 *  作为本轮记忆的默认对象)。记忆按 user 全局共享 → 跨线程可见(卖点)。 */
export function useCrm() {
  const [health, setHealth] = useState<Health | null>(null);
  const [people, setPeople] = useState<PersonListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [person, setPerson] = useState<Person | null>(null);
  const [ledger, setLedger] = useState<LedgerEvent[]>([]);
  const [asOf, setAsOf] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [thinking, setThinking] = useState(false); // 深度思考开关 (会话级偏好)
  const [ready, setReady] = useState(false); // 首屏加载完成 → 可发消息 (也消除发送/加载竞态)
  // 标记"刚在 sendTurn 里新建、并已乐观渲染首轮"的线程 id: 让随后那次切线程的空消息加载跳过一次,
  // 否则会把正在流式的气泡冲掉。一次性消费(见切线程 effect)。
  const freshSendRef = useRef<number | null>(null);

  // 闸门由账本派生: 只在"现在"视图展示(回看过去时不诱导确认历史提案)。
  const banners = useMemo<Banner[]>(
    () => (asOf == null ? pendingBanners(ledger) : []),
    [ledger, asOf],
  );

  const refreshPerson = useCallback(
    (id: number, at: string | null) => api.person(id, at).then(setPerson).catch(() => {}),
    [],
  );
  const refreshLedger = useCallback(
    (id: number) => api.ledger(id).then(setLedger).catch(() => {}),
    [],
  );
  const refreshPeople = useCallback(() => api.people().then(setPeople).catch(() => {}), []);
  const refreshConversations = useCallback(
    () => api.conversations().then(setConversations).catch(() => {}),
    [],
  );

  // 首屏: health + 联系人 + 对话线程。**不再"空则建一个"** —— 没有对话就停在草稿态
  // (居中迎接屏), 直到用户真正发出第一句才落库(见 sendTurn), 空对话永不进历史。
  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
    void (async () => {
      try {
        const ppl = await api.people().catch(() => [] as PersonListItem[]);
        setPeople(ppl);
        const firstPerson = ppl[0]?.id ?? null;
        const convs = await api.conversations().catch(() => [] as Conversation[]);
        setConversations(convs);
        const active = convs[0] ?? null;
        setActiveConvId(active?.id ?? null); // 有历史→选最近一条; 没有→null=草稿态
        setSelectedId(active?.focus_person_id ?? firstPerson);
      } finally {
        setReady(true);
      }
    })();
  }, []);

  // 切焦点联系人: 回"现在", 拉真相 + 账本 (账本一变, 闸门自动重算)
  useEffect(() => {
    if (selectedId == null) {
      setPerson(null);
      setLedger([]);
      return;
    }
    setAsOf(null);
    void refreshPerson(selectedId, null);
    void refreshLedger(selectedId);
  }, [selectedId, refreshPerson, refreshLedger]);

  // 切对话线程: 载入该线程消息
  useEffect(() => {
    if (activeConvId == null) {
      setMessages([]);
      return;
    }
    // 刚由 sendTurn 新建的线程已乐观渲染首轮 → 跳过这一次空加载(否则冲掉流式气泡)。一次性。
    if (freshSendRef.current === activeConvId) {
      freshSendRef.current = null;
      return;
    }
    let cancelled = false;
    api
      .messages(activeConvId)
      .then((ms) => {
        if (!cancelled) setMessages(ms.map(serverToChat));
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      });
    return () => {
      cancelled = true;
    };
  }, [activeConvId]);

  // 时光机: 把焦点真相拉到某时点 (null = 现在)
  const travelTo = useCallback(
    (at: string | null) => {
      setAsOf(at);
      if (selectedId != null) void refreshPerson(selectedId, at);
    },
    [selectedId, refreshPerson],
  );

  const selectConversation = useCallback(
    (id: number) => {
      if (id === activeConvId) return;
      setActiveConvId(id);
      const conv = conversations.find((c) => c.id === id);
      if (conv?.focus_person_id != null) setSelectedId(conv.focus_person_id);
    },
    [activeConvId, conversations],
  );

  // 新建对话 = 进入草稿态(清空舞台, 回到居中迎接屏), **不立即落库**。
  // 线程要等第一句真正发出时才创建(见 sendTurn) → 空对话永远不会出现在历史列表里。
  const newConversation = useCallback(() => {
    setActiveConvId(null);
    setMessages([]);
  }, []);

  const renameConversation = useCallback(async (id: number, title: string) => {
    const t = title.trim();
    if (!t) return;
    const c = await api.renameConversation(id, t).catch(() => null);
    if (c) setConversations((cs) => cs.map((x) => (x.id === id ? { ...x, title: c.title } : x)));
  }, []);

  const deleteConversation = useCallback(
    async (id: number) => {
      await api.deleteConversation(id).catch(() => {});
      const rest = conversations.filter((x) => x.id !== id);
      setConversations(rest);
      if (id !== activeConvId) return;
      // 删的是当前线程: 切到下一条; 一条不剩就回到草稿态(不再凭空建空对话)
      setActiveConvId(rest[0]?.id ?? null);
    },
    [conversations, activeConvId],
  );

  // ── 联系人 CRUD ──
  const createContact = useCallback(
    async (data: PersonInput) => {
      const p = await api.createPerson(data);
      await refreshPeople();
      setSelectedId(p.id);
      return p;
    },
    [refreshPeople],
  );

  const updateContact = useCallback(
    async (id: number, data: PersonInput) => {
      await api.updatePerson(id, data);
      await refreshPeople();
      if (id === selectedId) {
        setAsOf(null);
        void refreshPerson(id, null);
        void refreshLedger(id);
      }
    },
    [selectedId, refreshPeople, refreshPerson, refreshLedger],
  );

  const deleteContact = useCallback(
    async (id: number) => {
      await api.deletePerson(id);
      const rest = people.filter((p) => p.id !== id);
      await refreshPeople();
      void refreshConversations();
      if (id === selectedId) setSelectedId(rest[0]?.id ?? null);
    },
    [people, selectedId, refreshPeople, refreshConversations],
  );

  // 对话一轮: 流式回复 + 工具调用可视化 + 终态(真相/账本 → 闸门自动重算)
  const sendTurn = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (streaming || !trimmed) return;

      // 草稿态(尚未落库的新对话): 此刻——第一句真正发出——才创建线程, 之前不留空对话。
      // 用本地 convId(而非 activeConvId 异步态)发起本轮, 确保拿到的就是新线程 id。
      let convId = activeConvId;
      if (convId == null) {
        const created = await api.createConversation(selectedId).catch(() => null);
        if (!created) return;
        convId = created.id;
        freshSendRef.current = created.id; // 见切线程 effect: 别让空加载冲掉下面的乐观气泡
        setConversations((cs) => [created, ...cs]);
        setActiveConvId(created.id);
      }

      const aid = nextId();
      setMessages((m) => [
        ...m,
        { id: nextId(), role: "user", text: trimmed },
        { id: aid, role: "agent", text: "", tools: [], streaming: true },
      ]);
      setStreaming(true);
      setAsOf(null); // 跳回现在, 好让本轮写入(及其待确认闸门)可见

      const patchAgent = (fn: (msg: ChatMessage) => ChatMessage) =>
        setMessages((m) => m.map((msg) => (msg.id === aid ? fn(msg) : msg)));

      try {
        await streamTurn(trimmed, convId, selectedId, thinking, {
          onDelta: (t) => patchAgent((msg) => ({ ...msg, text: msg.text + t })),
          onReasoning: (t) =>
            patchAgent((msg) => ({ ...msg, reasoning: (msg.reasoning ?? "") + t })),
          onToolCall: (ev) =>
            patchAgent((msg) => ({
              ...msg,
              tools: upsertTool(msg.tools, {
                id: ev.id,
                name: ev.name,
                args: ev.args,
                status: "running",
              }),
            })),
          onToolResult: (ev) =>
            patchAgent((msg) => ({
              ...msg,
              tools: (msg.tools ?? []).map((t) =>
                t.id === ev.id ? { ...t, ok: ev.ok, status: ev.ok ? "done" : "error" } : t,
              ),
            })),
          onDone: (d) => {
            patchAgent((msg) => ({ ...msg, streaming: false }));
            if (d.error) patchAgent((msg) => ({ ...msg, text: msg.text || d.error || "" }));
            if (d.person) setPerson(d.person);
            if (d.ledger) setLedger(d.ledger); // 闸门由账本派生, 这里一刷新就出现
            void refreshPeople();
            void refreshConversations();
          },
        });
      } catch {
        patchAgent((msg) => ({
          ...msg,
          streaming: false,
          text: msg.text || "（请求失败，请稍后重试）",
        }));
      } finally {
        setStreaming(false);
      }
    },
    [activeConvId, selectedId, streaming, thinking, refreshPeople, refreshConversations],
  );

  // 确认闸门 / 消除拿不准: 采纳(confirm) 或 不改/消除(reject) → 刷新真相 + 账本 (闸门重算)
  const resolveBanner = useCallback(
    async (intentId: number, action: "confirm" | "reject") => {
      if (selectedId == null) return;
      try {
        if (action === "confirm") await api.confirm([intentId]);
        else await api.reject([intentId]);
      } finally {
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
    conversations,
    activeConvId,
    selectConversation,
    newConversation,
    renameConversation,
    deleteConversation,
    createContact,
    updateContact,
    deleteContact,
    messages,
    banners,
    streaming,
    ready,
    thinking,
    toggleThinking: () => setThinking((t) => !t),
    sendTurn,
    resolveBanner,
  };
}

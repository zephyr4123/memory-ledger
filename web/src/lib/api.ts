// 强类型 fetch 客户端。/api 在 dev 由 vite 代理、在 Docker 由 nginx 反代到后端。
import type {
  Conversation,
  ConvMessage,
  Health,
  LedgerEvent,
  Person,
  PersonInput,
  PersonListItem,
} from "./types";

const BASE = "/api";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

function send(method: string, path: string, body?: unknown): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    method,
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export const api = {
  health: () => fetch(`${BASE}/health`).then(asJson<Health>),

  people: () => fetch(`${BASE}/people`).then(asJson<PersonListItem[]>),

  person: (id: number, asOf?: string | null) => {
    const q = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
    return fetch(`${BASE}/people/${id}${q}`).then(asJson<Person>);
  },

  ledger: (id: number) => fetch(`${BASE}/people/${id}/ledger`).then(asJson<LedgerEvent[]>),

  createPerson: (data: PersonInput) => send("POST", "/people", data).then(asJson<Person>),

  updatePerson: (id: number, data: PersonInput) =>
    send("PATCH", `/people/${id}`, data).then(asJson<Person>),

  deletePerson: (id: number) =>
    send("DELETE", `/people/${id}`).then(asJson<{ ok: boolean; purged_intents: number }>),

  confirm: (ids: number[]) =>
    send("POST", "/intents/confirm", { intent_ids: ids }).then(asJson<{ affected: number }>),

  reject: (ids: number[], reason = "") =>
    send("POST", "/intents/reject", { intent_ids: ids, reason }).then(
      asJson<{ affected: number }>,
    ),

  // ── 对话线程 CRUD (跨对话记忆的载体) ──
  conversations: () => fetch(`${BASE}/conversations`).then(asJson<Conversation[]>),

  createConversation: (focusPersonId: number | null) =>
    send("POST", "/conversations", { focus_person_id: focusPersonId }).then(
      asJson<Conversation>,
    ),

  renameConversation: (id: number, title: string) =>
    send("PATCH", `/conversations/${id}`, { title }).then(asJson<Conversation>),

  deleteConversation: (id: number) =>
    send("DELETE", `/conversations/${id}`).then(asJson<{ ok: boolean }>),

  messages: (id: number) =>
    fetch(`${BASE}/conversations/${id}/messages`).then(asJson<ConvMessage[]>),
};

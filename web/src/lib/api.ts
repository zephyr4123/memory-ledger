// 强类型 fetch 客户端。/api 在 dev 由 vite 代理、在 Docker 由 nginx 反代到后端。
import type { Health, LedgerEvent, Person, PersonListItem } from "./types";

const BASE = "/api";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

function post(path: string, body: unknown): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
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

  confirm: (ids: number[]) =>
    post("/intents/confirm", { intent_ids: ids }).then(asJson<{ affected: number }>),

  reject: (ids: number[], reason = "") =>
    post("/intents/reject", { intent_ids: ids, reason }).then(asJson<{ affected: number }>),
};

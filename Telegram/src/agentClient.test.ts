import { test } from "node:test";
import assert from "node:assert/strict";
import { askAgent } from "./agentClient.js";

test("askAgent posts channel/external_id/text and the request ID header, and returns the reply", async () => {
  const originalFetch = globalThis.fetch;
  let capturedUrl: string | undefined;
  let capturedBody: unknown;
  let capturedRequestIdHeader: string | null | undefined;

  globalThis.fetch = (async (url: string, init: RequestInit) => {
    capturedUrl = url;
    capturedBody = JSON.parse(init.body as string);
    capturedRequestIdHeader = new Headers(init.headers).get("X-Request-Id");
    return new Response(JSON.stringify({ reply: "hi there" }), { status: 200 });
  }) as typeof fetch;

  try {
    const reply = await askAgent("chat-1", "hello", "req-1");
    assert.equal(reply, "hi there");
    assert.match(capturedUrl!, /\/chat$/);
    assert.deepEqual(capturedBody, { channel: "telegram", external_id: "chat-1", text: "hello" });
    assert.equal(capturedRequestIdHeader, "req-1");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("askAgent throws on a non-2xx response", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () => new Response("", { status: 500 })) as typeof fetch;

  try {
    await assert.rejects(() => askAgent("chat-1", "hello", "req-1"));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

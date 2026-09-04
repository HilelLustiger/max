import { test } from "node:test";
import assert from "node:assert/strict";
import type { Update, UserFromGetMe } from "grammy/types";
import { createBot } from "./bot.js";

const BOT_INFO: UserFromGetMe = {
  id: 1,
  is_bot: true,
  first_name: "Max",
  username: "max_bot",
  can_join_groups: true,
  can_read_all_group_messages: false,
  supports_inline_queries: false,
  can_connect_to_business: false,
  has_main_web_app: false,
  has_topics_enabled: false,
  allows_users_to_create_topics: false,
  can_manage_bots: false,
  supports_join_request_queries: false,
};

let nextUpdateId = 1;
let nextMessageId = 1;

function textUpdate(text: string): Update {
  return {
    update_id: nextUpdateId++,
    message: {
      message_id: nextMessageId++,
      date: Math.floor(Date.now() / 1000),
      chat: { id: 42, type: "private", first_name: "Ada" },
      from: { id: 42, is_bot: false, first_name: "Ada" },
      text,
      ...(text.startsWith("/")
        ? { entities: [{ type: "bot_command", offset: 0, length: text.length }] }
        : {}),
    },
  } as unknown as Update;
}

function photoUpdate(): Update {
  return {
    update_id: nextUpdateId++,
    message: {
      message_id: nextMessageId++,
      date: Math.floor(Date.now() / 1000),
      chat: { id: 42, type: "private", first_name: "Ada" },
      from: { id: 42, is_bot: false, first_name: "Ada" },
      photo: [{ file_id: "abc", file_unique_id: "abc", width: 100, height: 100 }],
    },
  } as unknown as Update;
}

function callbackQueryUpdate(data: string): Update {
  return {
    update_id: nextUpdateId++,
    callback_query: {
      id: `cb-${nextUpdateId}`,
      from: { id: 42, is_bot: false, first_name: "Ada" },
      chat_instance: "instance-1",
      data,
      message: {
        message_id: nextMessageId++,
        date: Math.floor(Date.now() / 1000),
        chat: { id: 42, type: "private", first_name: "Ada" },
        text: "When is it due?",
      },
    },
  } as unknown as Update;
}

/** Sets up a bot whose Telegram API calls are intercepted instead of hitting the network, per grammY's transformer-based testing pattern. */
async function createTestBot() {
  const bot = createBot("test-token", { botInfo: BOT_INFO });
  const sentMessages: string[] = [];
  const sentKeyboards: unknown[] = [];
  const answeredCallbacks: string[] = [];

  bot.api.config.use((_prev, method, payload) => {
    if (method === "sendMessage" && "text" in payload) {
      sentMessages.push(payload.text as string);
      sentKeyboards.push((payload as { reply_markup?: unknown }).reply_markup);
    }
    if (method === "answerCallbackQuery") {
      answeredCallbacks.push((payload as { callback_query_id: string }).callback_query_id);
    }
    return Promise.resolve({ ok: true, result: true } as never);
  });

  await bot.init();
  return { bot, sentMessages, sentKeyboards, answeredCallbacks };
}

test("message:text success path replies with the agent's response", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () =>
    new Response(JSON.stringify({ reply: "hi there" }), { status: 200 })) as typeof fetch;

  try {
    const { bot, sentMessages } = await createTestBot();
    await bot.handleUpdate(textUpdate("hello"));
    assert.deepEqual(sentMessages, ["hi there"]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("message:text fallback path replies with the fallback message when the agent call fails", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () => new Response("", { status: 500 })) as typeof fetch;

  try {
    const { bot, sentMessages } = await createTestBot();
    await bot.handleUpdate(textUpdate("hello"));
    assert.deepEqual(sentMessages, [
      "Sorry, I'm having trouble responding right now. Please try again in a moment.",
    ]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("/start replies with a greeting and does not call the agent", async () => {
  const originalFetch = globalThis.fetch;
  let fetchCalled = false;
  globalThis.fetch = (async () => {
    fetchCalled = true;
    return new Response(JSON.stringify({ reply: "hi there" }), { status: 200 });
  }) as typeof fetch;

  try {
    const { bot, sentMessages } = await createTestBot();
    await bot.handleUpdate(textUpdate("/start"));
    assert.equal(fetchCalled, false);
    assert.deepEqual(sentMessages, ["Hi! I'm Max. Send me a text message and I'll get back to you."]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("non-text updates get a friendly reply instead of being ignored", async () => {
  const { bot, sentMessages } = await createTestBot();
  await bot.handleUpdate(photoUpdate());
  assert.deepEqual(sentMessages, ["I can only handle text messages right now."]);
});

test("message:text clarification path replies with an inline keyboard instead of plain text", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({
        reply: "When is it due?",
        options: [
          { label: "Today", value: "2026-08-29" },
          { label: "Tomorrow", value: "2026-08-30" },
        ],
      }),
      { status: 200 },
    )) as typeof fetch;

  try {
    const { bot, sentMessages, sentKeyboards } = await createTestBot();
    await bot.handleUpdate(textUpdate("add a task"));
    assert.deepEqual(sentMessages, ["When is it due?"]);
    const keyboard = sentKeyboards[0] as { inline_keyboard: { text: string; callback_data: string }[][] };
    assert.deepEqual(
      keyboard.inline_keyboard.map((row) => row.map((button) => ({ text: button.text, value: button.callback_data }))),
      [[{ text: "Today", value: "2026-08-29" }], [{ text: "Tomorrow", value: "2026-08-30" }]],
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("callback_query press sends the selected option's value back to the agent and answers the callback", async () => {
  const originalFetch = globalThis.fetch;
  let capturedBody: unknown;
  globalThis.fetch = (async (_url: string, init: RequestInit) => {
    capturedBody = JSON.parse(init.body as string);
    return new Response(JSON.stringify({ reply: "✅ Task created" }), { status: 200 });
  }) as typeof fetch;

  try {
    const { bot, sentMessages, answeredCallbacks } = await createTestBot();
    await bot.handleUpdate(callbackQueryUpdate("2026-08-29"));
    assert.deepEqual(capturedBody, { channel: "telegram", external_id: "42", text: "2026-08-29" });
    assert.deepEqual(sentMessages, ["✅ Task created"]);
    assert.equal(answeredCallbacks.length, 1);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("an option with an empty value gets a non-empty callback_data placeholder (Telegram rejects empty callback_data)", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({
        reply: "When is it due?",
        options: [{ label: "No due date", value: "" }],
      }),
      { status: 200 },
    )) as typeof fetch;

  try {
    const { bot, sentKeyboards } = await createTestBot();
    await bot.handleUpdate(textUpdate("add a task"));
    const keyboard = sentKeyboards[0] as { inline_keyboard: { text: string; callback_data: string }[][] };
    const button = keyboard.inline_keyboard[0][0];
    assert.equal(button.text, "No due date");
    assert.notEqual(button.callback_data, "");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("pressing the empty-value placeholder button sends an empty string back to the agent", async () => {
  const originalFetch = globalThis.fetch;
  let capturedBody: unknown;
  globalThis.fetch = (async (_url: string, init: RequestInit) => {
    capturedBody = JSON.parse(init.body as string);
    return new Response(JSON.stringify({ reply: "✅ Task created" }), { status: 200 });
  }) as typeof fetch;

  try {
    const { bot } = await createTestBot();
    await bot.handleUpdate(callbackQueryUpdate("__empty__"));
    assert.deepEqual(capturedBody, { channel: "telegram", external_id: "42", text: "" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

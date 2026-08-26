import { Bot } from "grammy";
import { config } from "./config.js";
import { askAgent } from "./agentClient.js";

const FALLBACK_REPLY = "Sorry, I'm having trouble responding right now. Please try again in a moment.";

export function createBot(): Bot {
  const bot = new Bot(config.telegramBotToken);

  bot.on("message:text", async (ctx) => {
    const chatId = String(ctx.chat.id);
    try {
      const reply = await askAgent(chatId, ctx.message.text);
      await ctx.reply(reply);
    } catch (error) {
      console.error(JSON.stringify({ event: "agent_call_failed", chat_id: chatId, error: String(error) }));
      await ctx.reply(FALLBACK_REPLY);
    }
  });

  return bot;
}

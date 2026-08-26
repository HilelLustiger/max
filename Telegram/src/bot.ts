import { randomUUID } from "node:crypto";
import { Bot } from "grammy";
import { config } from "./config.js";
import { askAgent } from "./agentClient.js";
import { logger } from "./logger.js";

const FALLBACK_REPLY = "Sorry, I'm having trouble responding right now. Please try again in a moment.";

export function createBot(): Bot {
  const bot = new Bot(config.telegramBotToken);

  bot.on("message:text", async (ctx) => {
    const chatId = String(ctx.chat.id);
    const requestId = randomUUID();
    logger.info("message_received", { request_id: requestId, chat_id: chatId });

    try {
      const reply = await askAgent(chatId, ctx.message.text, requestId);
      await ctx.reply(reply);
      logger.info("reply_sent", { request_id: requestId, chat_id: chatId });
    } catch (error) {
      logger.error("agent_call_failed", { request_id: requestId, chat_id: chatId, error: String(error) });
      await ctx.reply(FALLBACK_REPLY);
    }
  });

  return bot;
}

import { randomUUID } from "node:crypto";
import { Bot, InlineKeyboard, type BotConfig, type Context } from "grammy";
import { config } from "./config.js";
import { askAgent } from "./agentClient.js";
import { logger } from "./logger.js";

const FALLBACK_REPLY = "Sorry, I'm having trouble responding right now. Please try again in a moment.";
const START_REPLY = "Hi! I'm Max. Send me a text message and I'll get back to you.";
const UNSUPPORTED_REPLY = "I can only handle text messages right now.";

async function replyWithAgentResponse(
  ctx: Context,
  chatId: string,
  text: string,
  requestId: string,
): Promise<void> {
  const response = await askAgent(chatId, text, requestId);
  if (response.clarification) {
    const keyboard = new InlineKeyboard(
      response.clarification.options.map((option) => [InlineKeyboard.text(option, option)]),
    );
    await ctx.reply(response.clarification.question, { reply_markup: keyboard });
  } else {
    await ctx.reply(response.reply);
  }
}

export function createBot(token: string = config.telegramBotToken, options?: BotConfig<Context>): Bot {
  const bot = new Bot(token, options);

  bot.command("start", async (ctx) => {
    await ctx.reply(START_REPLY);
  });

  bot.on("message:text", async (ctx) => {
    const chatId = String(ctx.chat.id);
    const requestId = randomUUID();
    logger.info("message_received", { request_id: requestId, chat_id: chatId });

    try {
      await replyWithAgentResponse(ctx, chatId, ctx.message.text, requestId);
      logger.info("reply_sent", { request_id: requestId, chat_id: chatId });
    } catch (error) {
      logger.error("agent_call_failed", { request_id: requestId, chat_id: chatId, error: String(error) });
      await ctx.reply(FALLBACK_REPLY);
    }
  });

  bot.on("callback_query:data", async (ctx) => {
    if (!ctx.chat) return;
    const chatId = String(ctx.chat.id);
    const requestId = randomUUID();
    const selectedOption = ctx.callbackQuery.data;
    logger.info("callback_query_received", { request_id: requestId, chat_id: chatId });

    await ctx.answerCallbackQuery();
    try {
      await replyWithAgentResponse(ctx, chatId, selectedOption, requestId);
      logger.info("reply_sent", { request_id: requestId, chat_id: chatId });
    } catch (error) {
      logger.error("agent_call_failed", { request_id: requestId, chat_id: chatId, error: String(error) });
      await ctx.reply(FALLBACK_REPLY);
    }
  });

  bot.on("message", async (ctx) => {
    await ctx.reply(UNSUPPORTED_REPLY);
  });

  return bot;
}

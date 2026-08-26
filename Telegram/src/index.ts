import { createBot } from "./bot.js";
import { logger } from "./logger.js";

const bot = createBot();

bot.start({
  onStart: () => logger.info("bot_started"),
});

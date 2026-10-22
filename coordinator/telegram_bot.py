"""Telegram Bot interface for remote laptop control.
Zero admin rights, zero port forwarding, works through NAT and firewalls seamlessly.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from common.models import ClusterSplitPlan, ClusterStatus, InferenceResponse
from common.utils import format_bar, format_mb


logger = logging.getLogger("TelegramBot")


class ClusterTelegramBot:
    """Controls the distributed cluster remotely from a laptop via Telegram."""

    def __init__(
        self,
        bot_token: str,
        authorized_chat_ids: List[int],
        coordinator_ref: Any,
    ):
        self.bot_token = bot_token
        self.authorized_chat_ids = set(authorized_chat_ids)
        self.coordinator = coordinator_ref
        self.application: Optional[Application] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _is_authorized(self, update: Update) -> bool:
        if not update.effective_chat:
            return False
        chat_id = update.effective_chat.id
        # If no chat IDs are configured yet, authorize the first user who runs /start
        if not self.authorized_chat_ids:
            self.authorized_chat_ids.add(chat_id)
            logger.info(f"Auto-authorized initial Telegram Chat ID: {chat_id}")
            return True
        return chat_id in self.authorized_chat_ids

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized. Your Chat ID is not whitelisted.")
            return

        welcome_text = (
            "🚀 *Distributed AI & RAM Mesh Controller*\n\n"
            "Control your LAN AI cluster remotely from this laptop/device!\n\n"
            "*Available Commands:*\n"
            "📦 `/models` - List downloaded local AI models (LM Studio & files)\n"
            "🚀 `/load <id>` - Automatically split & deploy model across cluster\n"
            "⏹️ `/unload` - Unload active model & free all cluster RAM\n"
            "🖥️ `/pcs` - Exact count & full directory of all connected PCs\n"
            "📊 `/status` - Cluster overview, PC count & live RAM usage\n"
            "💾 `/ram` - Deep memory metrics per worker PC\n"
            "🌐 `/nodes` - List LAN IP addresses and RPC ports\n"
            "⚡ `/split [layers]` - Dynamic layer allocation for LLMs\n"
            "🧹 `/clean` - Purge & trim working set RAM across all nodes\n"
            "▶️ `/start_workers` - Launch RPC backends on all nodes\n"
            "⏹️ `/stop_workers` - Stop all worker backends\n"
            "🛡️ `/guard [mb]` - View or set OOM safety threshold\n"
            "💬 `/ask <prompt>` - Run distributed inference across cluster\n"
            "❓ `/help` - Show this guide"
        )
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_pcs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        status: ClusterStatus = self.coordinator.get_cluster_status()
        nodes = list(status.nodes.values())
        online_count = status.online_nodes
        offline_count = max(0, status.total_nodes - online_count)

        msg = (
            f"🖥️ *Cluster PC Count & Status*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Total Registered PCs:* `{status.total_nodes}`\n"
            f"• *🟢 Online PCs:* `{online_count}`\n"
            f"• *🔴 Offline PCs:* `{offline_count}`\n\n"
        )

        if not nodes:
            msg += "_No worker PCs are currently registered._\n_Run `start_worker.bat` on your LAN computers to connect them._"
        else:
            msg += "*Connected PCs Directory:*\n"
            for i, node in enumerate(nodes, 1):
                state_emoji = "🟢" if node.status == "online" else "🔴"
                rpc_status = "RPC: ON" if node.rpc_running else "RPC: OFF"
                msg += (
                    f"{i}. {state_emoji} *{node.node_id}* (`{node.ip_address}`)\n"
                    f"   • Status: `{node.status.upper()}` | CPU: `{node.cpu_percent:.0f}%`\n"
                    f"   • Free RAM: `{format_mb(node.memory.avail_ram_mb)}` / `{format_mb(node.memory.total_ram_mb)}`\n"
                    f"   • Backend: `{rpc_status}` (Port `{node.rpc_port}`)\n"
                )

        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        status: ClusterStatus = self.coordinator.get_cluster_status()
        tot_ram_gb = status.total_cluster_ram_gb
        free_ram_gb = status.free_cluster_ram_gb
        used_ram_gb = max(0.0, tot_ram_gb - free_ram_gb)
        used_pct = (used_ram_gb / tot_ram_gb * 100.0) if tot_ram_gb > 0 else 0.0

        bar = format_bar(used_pct, width=12)

        msg = (
            f"🌐 *Cluster Status:* `{status.cluster_name}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• *🖥️ Connected PCs:* `{status.online_nodes} Online` (`{status.total_nodes} Total`)\n"
            f"• *Cluster RAM:* `{used_ram_gb:.1f} GB / {tot_ram_gb:.1f} GB` ({used_pct:.0f}%)\n"
            f"  `[{bar}]`\n"
            f"• *Available Free RAM:* `{free_ram_gb:.2f} GB`\n\n"
            f"*Connected PCs:*\n"
        )

        if not status.nodes:
            msg += "_No worker PCs currently connected._"
        else:
            for node_id, node in status.nodes.items():
                mem = node.memory
                node_used_pct = mem.percent_used
                state_emoji = "🟢" if node.status == "online" else ("🔴" if node.status == "offline" else "⚠️")
                rpc_status = "RPC: ON" if node.rpc_running else "RPC: OFF"
                vram_str = f" | VRAM: {mem.vram_free_mb:.0f}MB" if mem.vram_free_mb else ""

                msg += (
                    f"{state_emoji} *{node.node_id}* (`{node.ip_address}`)\n"
                    f"   RAM: `{format_mb(mem.avail_ram_mb)} free` ({node_used_pct:.0f}% used) | CPU: `{node.cpu_percent:.0f}%`\n"
                    f"   [{rpc_status}{vram_str}]\n"
                )

        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_ram(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        status: ClusterStatus = self.coordinator.get_cluster_status()
        if not status.nodes:
            await update.message.reply_text("No worker nodes connected.")
            return

        msg = "💾 *Node-by-Node Memory Breakdown*\n━━━━━━━━━━━━━━━━━━━━\n"
        for node_id, node in status.nodes.items():
            m = node.memory
            msg += (
                f"🖥️ *{node.node_id}* ({node.ip_address})\n"
                f"• Physical Total: `{format_mb(m.total_ram_mb)}`\n"
                f"• Physical Free:  `{format_mb(m.avail_ram_mb)}`\n"
                f"• Memory Load:    `{m.percent_used:.1f}%`\n"
                f"• Pagefile Free:  `{format_mb(m.swap_avail_mb)}`\n"
                f"• Process RAM:    `{format_mb(m.process_ram_mb)}`\n"
            )
            if m.vram_total_mb:
                msg += f"• GPU VRAM Free:  `{format_mb(m.vram_free_mb)}` / `{format_mb(m.vram_total_mb)}`\n"
            if m.is_oom_critical:
                msg += "⚠️ *OOM RISK: Free memory below critical threshold!*\n"
            msg += "\n"

        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_nodes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        nodes = self.coordinator.get_nodes()
        if not nodes:
            await update.message.reply_text("No worker PCs registered yet.")
            return

        online_count = sum(1 for n in nodes if n.status == "online")
        offline_count = max(0, len(nodes) - online_count)

        msg = (
            f"🖥️ *Cluster Nodes & LAN Directory*\n"
            f"Total PCs: `{len(nodes)}` (🟢 Online: `{online_count}`, 🔴 Offline: `{offline_count}`)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )
        for i, node in enumerate(nodes, 1):
            state_emoji = "🟢" if node.status == "online" else "🔴"
            msg += (
                f"{i}. {state_emoji} *{node.node_id}* ({node.hostname})\n"
                f"   • LAN Address: `{node.ip_address}:{node.port}`\n"
                f"   • RPC Endpoint: `{node.ip_address}:{node.rpc_port}`\n"
                f"   • Status: `{node.status.upper()}` | RPC: `{node.rpc_running}`\n"
            )
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_split(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        args = context.args or []
        layers = int(args[0]) if args and args[0].isdigit() else 32

        plan: ClusterSplitPlan = self.coordinator.calculate_split_plan(total_layers=layers)

        msg = (
            f"⚡ *Dynamic Layer Split for {layers} Layers*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"• Usable Headroom: `{format_mb(plan.total_available_ram_mb)}`\n\n"
        )

        for alloc in plan.allocations:
            msg += (
                f"• *{alloc.node_id}*: `{alloc.layers} layers` (L{alloc.start_layer} - L{alloc.end_layer})\n"
                f"  Usable RAM: `{format_mb(alloc.usable_ram_mb)}` | Assigned: ~`{format_mb(alloc.assigned_ram_mb)}`\n"
            )

        if plan.rpc_endpoints:
            endpoints_str = ",".join(plan.rpc_endpoints)
            msg += f"\n*llama.cpp RPC Flag:*\n`--rpc {endpoints_str}`\n"

        if plan.warnings:
            for w in plan.warnings:
                msg += f"\n⚠️ _{w}_"

        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_clean(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        await update.message.reply_text("🧹 Initiating RAM trim and garbage collection across all LAN nodes...")
        results = await self.coordinator.trim_all_nodes()
        total_freed = sum(r.get("freed_ram_mb", 0.0) for r in results.values())

        msg = (
            f"✨ *RAM Trim Complete!*\n"
            f"Total Memory Recovered: `{format_mb(total_freed)}`\n\n"
        )
        for nid, r in results.items():
            msg += f"• *{nid}*: Freed `{r.get('freed_ram_mb', 0.0):.1f} MB` (Now: `{format_mb(r.get('available_ram_mb', 0.0))}` free)\n"

        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_start_workers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        await update.message.reply_text("▶️ Starting RPC workers across all LAN nodes...")
        results = await self.coordinator.start_all_rpc_workers()
        msg = "🚀 *RPC Startup Results:*\n"
        for nid, res in results.items():
            msg += f"• *{nid}*: {res.get('message', 'Done')}\n"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_stop_workers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        await update.message.reply_text("⏹️ Stopping RPC workers across all LAN nodes...")
        results = await self.coordinator.stop_all_rpc_workers()
        msg = "🛑 *RPC Stop Results:*\n"
        for nid, res in results.items():
            msg += f"• *{nid}*: {res.get('message', 'Stopped')}\n"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_guard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        args = context.args or []
        if args and args[0].isdigit():
            new_mb = float(args[0])
            self.coordinator.set_guard_threshold(new_mb)
            await update.message.reply_text(f"🛡️ OOM Guard threshold updated to `{new_mb:.0f} MB`.")
        else:
            current = self.coordinator.get_guard_threshold()
            await update.message.reply_text(
                f"🛡️ Current OOM Guard safety threshold: `{current:.0f} MB`.\n"
                f"To change, send: `/guard <megabytes>` (e.g. `/guard 1000`)"
            )

    async def _cmd_ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        prompt = " ".join(context.args) if context.args else ""
        if not prompt:
            await update.message.reply_text("Please provide a prompt: `/ask What is distributed inference?`")
            return

        status_msg = await update.message.reply_text(f"🤖 Dispatching inference across cluster...\nPrompt: _{prompt[:50]}..._")

        response: InferenceResponse = await self.coordinator.execute_inference(prompt)
        if response.success:
            reply = (
                f"💬 *Cluster Output:*\n{response.text}\n\n"
                f"⏱️ _Generated {response.tokens_generated} tokens in {response.elapsed_sec:.2f}s_"
            )
        else:
            reply = f"❌ *Inference Error:*\n`{response.error}`"

        await status_msg.edit_text(reply, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_models(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        models = await self.coordinator.get_cluster_models()
        if not models:
            await update.message.reply_text("No local models found in LM Studio or models/ folders.")
            return

        msg = "📦 *Local Models Found Across Cluster (LM Studio)*\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, m in enumerate(models, 1):
            msg += (
                f"{i}. *{m.name}*\n"
                f"   • Size: `{m.size_gb} GB` | Arch: `{m.architecture}` | Layers: `{m.layers}`\n"
                f"   • Source: `{m.source}` | PC: `{m.node_id or 'LAN'}`\n"
            )
        msg += "\n*To run on cluster:* `/load <number>` (e.g. `/load 1`)"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_load(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        args = context.args or []
        if not args:
            await update.message.reply_text("Please specify model number or name: `/load 1`")
            return

        ident = args[0]
        models = await self.coordinator.get_cluster_models()
        target = None

        if ident.isdigit():
            idx = int(ident) - 1
            if 0 <= idx < len(models):
                target = models[idx]
        else:
            for m in models:
                if ident.lower() in m.name.lower():
                    target = m
                    break

        model_name = target.name if target else ident
        layers = target.layers if target else 32

        await update.message.reply_text(f"🚀 Configuring cluster & deploying *{model_name}* ({layers} layers)...", parse_mode=ParseMode.MARKDOWN)

        plan = self.coordinator.calculate_split_plan(total_layers=layers, model_name=model_name)
        if not plan.is_viable:
            await update.message.reply_text(f"❌ Cannot load model: cluster free RAM is insufficient.\n{plan.warnings}")
            return

        await self.coordinator.start_all_rpc_workers()

        msg = (
            f"✅ *Model '{model_name}' Active on Cluster!*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )
        for a in plan.allocations:
            msg += f"• *{a.node_id}*: `{a.layers} layers` (L{a.start_layer}-L{a.end_layer}) | RAM: ~`{format_mb(a.assigned_ram_mb)}`\n"

        msg += "\n💬 Ask questions anytime using `/ask <prompt>`"
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def _cmd_unload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return

        await self.coordinator.stop_all_rpc_workers()
        await update.message.reply_text("⏹️ Active model unloaded. All worker RAM released.")

    def send_broadcast_alert(self, alert_text: str):
        """Send push notification alert to authorized Telegram chat IDs."""
        if not self.application or not self.authorized_chat_ids:
            return

        async def _do_send():
            for chat_id in self.authorized_chat_ids:
                try:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=f"🚨 *CLUSTER ALERT*\n{alert_text}",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as e:
                    logger.error(f"Failed to push alert to {chat_id}: {e}")

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(_do_send(), self._loop)

    def start_polling(self, loop: asyncio.AbstractEventLoop):
        """Initialize and start telegram bot polling."""
        self._loop = loop
        self.application = ApplicationBuilder().token(self.bot_token).build()

        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("help", self._cmd_start))
        self.application.add_handler(CommandHandler("models", self._cmd_models))
        self.application.add_handler(CommandHandler("load", self._cmd_load))
        self.application.add_handler(CommandHandler("unload", self._cmd_unload))
        self.application.add_handler(CommandHandler("pcs", self._cmd_pcs))
        self.application.add_handler(CommandHandler("count", self._cmd_pcs))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_handler(CommandHandler("ram", self._cmd_ram))
        self.application.add_handler(CommandHandler("nodes", self._cmd_nodes))
        self.application.add_handler(CommandHandler("split", self._cmd_split))
        self.application.add_handler(CommandHandler("clean", self._cmd_clean))
        self.application.add_handler(CommandHandler("start_workers", self._cmd_start_workers))
        self.application.add_handler(CommandHandler("stop_workers", self._cmd_stop_workers))
        self.application.add_handler(CommandHandler("guard", self._cmd_guard))
        self.application.add_handler(CommandHandler("ask", self._cmd_ask))

        return self.application

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
from datetime import timedelta

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.moderation = True

bot = commands.Bot(command_prefix="!", intents=intents)

GUILD_ID = discord.Object(id=1527211533845659728)

ARCHIVO_CONFIG = "bienvenida.json"
NOMBRE_CANAL_LOGS = "historial-jugadores"

CONFIG_DEFAULT = {
    "canal_id": None,
    "rol_id": None,
    "texto": "👋 • Bienvenido/a {mention} a **{server}**\n\n🌊 • Lee las normas y entra al server a disfrutar\n\n💎 • IP: Próximamente",
    "embed": "Hola {mention}.\n\nGracias por unirte. Tu ID es `{userId}` y eres el miembro **#{memberCount}**.",
    "color": "0071ba"
}

def cargar_config():
    if os.path.exists(ARCHIVO_CONFIG):
        with open(ARCHIVO_CONFIG, "r", encoding="utf-8") as f:
            return json.load(f)
    return CONFIG_DEFAULT.copy()

def guardar_config(config):
    with open(ARCHIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

async def canal_logs(guild):
    return discord.utils.get(guild.text_channels, name=NOMBRE_CANAL_LOGS)

# --- Sistema anti-nuke ---
acciones_canal_rol = {}
acciones_ban_kick = {}
VENTANA_SEGUNDOS = 15
UMBRAL_BORRADOS = 3
UMBRAL_BANEOS = 4

async def anti_nuke_banear(guild, autor, motivo):
    try:
        await guild.ban(autor, reason=motivo)
        canal = await canal_logs(guild)
        if canal:
            await canal.send(f"🚨 **ANTI-NUKE**: {autor} ha sido baneado automáticamente.\nMotivo: {motivo}")
        print(f"🛡️ Anti-nuke: {autor} baneado — {motivo}")
    except Exception as e:
        print(f"❌ Error en anti-nuke al banear: {e}")

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    try:
        bot.tree.copy_global_to(guild=GUILD_ID)
        sincronizados = await bot.tree.sync(guild=GUILD_ID)
        print(f"Comandos slash sincronizados en el servidor: {len(sincronizados)}")
    except Exception as e:
        print(f"❌ ERROR AL SINCRONIZAR: {e}")

@bot.tree.command(name="ping", description="Comprueba si el bot responde")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")
@bot.event
async def on_member_join(member):
    config = cargar_config()

    if config.get("rol_id"):
        rol = member.guild.get_role(config["rol_id"])
        if rol:
            await member.add_roles(rol)
        else:
            print(f"⚠️ No se encontró el rol con ID {config['rol_id']}")

    if config.get("canal_id"):
        canal = member.guild.get_channel(config["canal_id"])
        if canal:
            texto = config["texto"].format(mention=member.mention, server=member.guild.name)
            await canal.send(texto)

            texto_embed = config["embed"].format(
                mention=member.mention,
                userId=member.id,
                memberCount=member.guild.member_count
            )
            embed = discord.Embed(
                description=texto_embed,
                color=discord.Color(int(config["color"], 16))
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await canal.send(embed=embed)
        else:
            print(f"⚠️ No se encontró el canal con ID {config['canal_id']}")

@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        autor = entry.user
        ahora = time.time()
        lista = acciones_canal_rol.setdefault(autor.id, [])
        lista.append(ahora)
        while lista and lista[0] < ahora - VENTANA_SEGUNDOS:
            lista.pop(0)
        if len(lista) >= UMBRAL_BORRADOS:
            await anti_nuke_banear(guild, autor, "Borrado masivo de canales")

@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        autor = entry.user
        ahora = time.time()
        lista = acciones_canal_rol.setdefault(autor.id, [])
        lista.append(ahora)
        while lista and lista[0] < ahora - VENTANA_SEGUNDOS:
            lista.pop(0)
        if len(lista) >= UMBRAL_BORRADOS:
            await anti_nuke_banear(guild, autor, "Borrado masivo de roles")

@bot.event
async def on_guild_role_create(role):
    if role.permissions.administrator:
        guild = role.guild
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
            autor = entry.user
            await anti_nuke_banear(guild, autor, "Creación sospechosa de rol con permisos de Administrador")

@bot.event
async def on_member_ban(guild, user):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        autor = entry.user
        if autor.id == bot.user.id:
            return
        ahora = time.time()
        lista = acciones_ban_kick.setdefault(autor.id, [])
        lista.append(ahora)
        while lista and lista[0] < ahora - VENTANA_SEGUNDOS:
            lista.pop(0)
        if len(lista) >= UMBRAL_BANEOS:
            await anti_nuke_banear(guild, autor, "Baneos masivos sospechosos")
@bot.tree.command(name="setbienvenidatexto", description="Cambia el mensaje de bienvenida (texto)")
@app_commands.checks.has_permissions(administrator=True)
async def setbienvenidatexto(interaction: discord.Interaction, nuevo_texto: str):
    config = cargar_config()
    config["texto"] = nuevo_texto
    guardar_config(config)
    await interaction.response.send_message("✅ Mensaje de bienvenida (texto) actualizado.")

@bot.tree.command(name="setbienvenidaembed", description="Cambia el mensaje de bienvenida (embed)")
@app_commands.checks.has_permissions(administrator=True)
async def setbienvenidaembed(interaction: discord.Interaction, nuevo_texto: str):
    config = cargar_config()
    config["embed"] = nuevo_texto
    guardar_config(config)
    await interaction.response.send_message("✅ Mensaje de bienvenida (embed) actualizado.")

@bot.tree.command(name="setbienvenidacanal", description="Cambia el canal de bienvenida")
@app_commands.checks.has_permissions(administrator=True)
async def setbienvenidacanal(interaction: discord.Interaction, canal: discord.TextChannel):
    config = cargar_config()
    config["canal_id"] = canal.id
    guardar_config(config)
    await interaction.response.send_message(f"✅ Canal de bienvenida cambiado a: {canal.mention}")

@bot.tree.command(name="setbienvenidarol", description="Cambia el rol automático al entrar")
@app_commands.checks.has_permissions(administrator=True)
async def setbienvenidarol(interaction: discord.Interaction, rol: discord.Role):
    config = cargar_config()
    config["rol_id"] = rol.id
    guardar_config(config)
    await interaction.response.send_message(f"✅ Rol automático cambiado a: {rol.mention}")

@bot.tree.command(name="setbienvenidacolor", description="Cambia el color del embed de bienvenida")
@app_commands.checks.has_permissions(administrator=True)
async def setbienvenidacolor(interaction: discord.Interaction, hex_color: str):
    config = cargar_config()
    config["color"] = hex_color.replace("#", "")
    guardar_config(config)
    await interaction.response.send_message(f"✅ Color del embed actualizado a #{config['color']}")
@bot.tree.command(name="kick", description="Expulsa a un usuario del servidor")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sin motivo especificado"):
    await usuario.kick(reason=motivo)
    await interaction.response.send_message(f"👢 {usuario.mention} ha sido expulsado.\nMotivo: {motivo}")

@bot.tree.command(name="ban", description="Banea a un usuario del servidor")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, usuario: discord.Member, motivo: str = "Sin motivo especificado"):
    await usuario.ban(reason=motivo)
    await interaction.response.send_message(f"🔨 {usuario.mention} ha sido baneado.\nMotivo: {motivo}")

@bot.tree.command(name="timeout", description="Silencia temporalmente a un usuario (en minutos)")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, usuario: discord.Member, minutos: int, motivo: str = "Sin motivo especificado"):
    duracion = discord.utils.utcnow() + timedelta(minutes=minutos)
    await usuario.timeout(duracion, reason=motivo)
    await interaction.response.send_message(f"🔇 {usuario.mention} ha sido silenciado por {minutos} minutos.\nMotivo: {motivo}")
@bot.tree.command(name="warn", description="Da un aviso a un usuario")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, usuario: discord.Member, motivo: str):
    canal = await canal_logs(interaction.guild)
    if canal:
        await canal.send(f"⚠️ **AVISO** a {usuario.mention} (por {interaction.user.mention})\nMotivo: {motivo}")

    try:
        await usuario.send(f"⚠️ Has recibido un aviso en **{interaction.guild.name}**.\nMotivo: {motivo}")
    except discord.Forbidden:
        print(f"⚠️ No se pudo enviar MD a {usuario} (tiene los MDs cerrados)")

    await interaction.response.send_message(f"⚠️ {usuario.mention} ha recibido un aviso.\nMotivo: {motivo}")

@bot.tree.command(name="clear", description="Borra una cantidad de mensajes del canal")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, cantidad: int):
    await interaction.response.defer(ephemeral=True)
    borrados = await interaction.channel.purge(limit=cantidad)
    await interaction.followup.send(f"🧹 Se borraron {len(borrados)} mensajes.", ephemeral=True)

@bot.tree.command(name="unban", description="Quita el baneo a un usuario")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str, motivo: str = "Sin motivo especificado"):
    usuario = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(usuario, reason=motivo)
    await interaction.response.send_message(f"✅ {usuario.mention} ha sido desbaneado.\nMotivo: {motivo}")

@bot.tree.command(name="untimeout", description="Quita el silencio a un usuario")
@app_commands.checks.has_permissions(moderate_members=True)
async def untimeout(interaction: discord.Interaction, usuario: discord.Member):
    await usuario.timeout(None)
    await interaction.response.send_message(f"🔊 {usuario.mention} ya no está silenciado.")


import os
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)
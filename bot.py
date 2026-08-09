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

ARCHIVO_SUGERENCIAS = "sugerencias.json"

CONFIG_SUG_DEFAULT = {
    "canal_crear_id": None,
    "canal_buzon_id": None,
    "canal_staff_id": None
}

def cargar_config_sug():
    if os.path.exists(ARCHIVO_SUGERENCIAS):
        with open(ARCHIVO_SUGERENCIAS, "r", encoding="utf-8") as f:
            return json.load(f)
    return CONFIG_SUG_DEFAULT.copy()

def guardar_config_sug(config):
    with open(ARCHIVO_SUGERENCIAS, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

async def canal_logs(guild):
    return discord.utils.get(guild.text_channels, name=NOMBRE_CANAL_LOGS)
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

class VotosPublicoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.apoyos = 0
        self.no_apoyos = 0

    @discord.ui.button(label="Apoyar", style=discord.ButtonStyle.success, emoji="👍", custom_id="sugerencia_apoyar")
    async def apoyar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.apoyos += 1
        self.children[0].label = f"Apoyar ({self.apoyos})"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="No apoyar", style=discord.ButtonStyle.danger, emoji="👎", custom_id="sugerencia_no_apoyar")
    async def no_apoyar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.no_apoyos += 1
        self.children[1].label = f"No apoyar ({self.no_apoyos})"
        await interaction.response.edit_message(view=self)

class VotosStaffView(discord.ui.View):
    def __init__(self, mensaje_publico_id, canal_publico_id):
        super().__init__(timeout=None)
        self.mensaje_publico_id = mensaje_publico_id
        self.canal_publico_id = canal_publico_id

    @discord.ui.button(label="Aceptar", style=discord.ButtonStyle.primary, emoji="✅", custom_id="staff_aceptar")
    async def aceptar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores.", ephemeral=True)
            return
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.set_footer(text=f"✅ Aceptada por {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed, view=None)
        await self.actualizar_publico(interaction.guild, embed)

    @discord.ui.button(label="Rechazar", style=discord.ButtonStyle.danger, emoji="❌", custom_id="staff_rechazar")
    async def rechazar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Solo administradores.", ephemeral=True)
            return
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.set_footer(text=f"❌ Rechazada por {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed, view=None)
        await self.actualizar_publico(interaction.guild, embed)

    async def actualizar_publico(self, guild, embed):
        canal = guild.get_channel(self.canal_publico_id)
        if canal:
            try:
                mensaje = await canal.fetch_message(self.mensaje_publico_id)
                await mensaje.edit(embed=embed)
            except Exception as e:
                print(f"⚠️ No se pudo actualizar el mensaje público: {e}")

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    bot.add_view(VotosPublicoView())
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
@bot.tree.command(name="setcanalcrearsugerencia", description="Canal donde se puede usar /sugerencia")
@app_commands.checks.has_permissions(administrator=True)
async def setcanalcrearsugerencia(interaction: discord.Interaction, canal: discord.TextChannel):
    config = cargar_config_sug()
    config["canal_crear_id"] = canal.id
    guardar_config_sug(config)
    await interaction.response.send_message(f"✅ Canal para crear sugerencias: {canal.mention}")

@bot.tree.command(name="setcanalbuzonsugerencias", description="Canal público donde se publican las sugerencias")
@app_commands.checks.has_permissions(administrator=True)
async def setcanalbuzonsugerencias(interaction: discord.Interaction, canal: discord.TextChannel):
    config = cargar_config_sug()
    config["canal_buzon_id"] = canal.id
    guardar_config_sug(config)
    await interaction.response.send_message(f"✅ Canal buzón de sugerencias: {canal.mention}")

@bot.tree.command(name="setcanalstaffsugerencias", description="Canal de staff para aceptar/rechazar sugerencias")
@app_commands.checks.has_permissions(administrator=True)
async def setcanalstaffsugerencias(interaction: discord.Interaction, canal: discord.TextChannel):
    config = cargar_config_sug()
    config["canal_staff_id"] = canal.id
    guardar_config_sug(config)
    await interaction.response.send_message(f"✅ Canal de staff para sugerencias: {canal.mention}")

@bot.tree.command(name="sugerencia", description="Envía una sugerencia al buzón")
async def sugerencia(interaction: discord.Interaction, texto: str):
    config = cargar_config_sug()

    if config.get("canal_crear_id") and interaction.channel.id != config["canal_crear_id"]:
        canal_correcto = interaction.guild.get_channel(config["canal_crear_id"])
        await interaction.response.send_message(
            f"⚠️ Solo puedes enviar sugerencias en {canal_correcto.mention}", ephemeral=True
        )
        return

    if not config.get("canal_buzon_id") or not config.get("canal_staff_id"):
        await interaction.response.send_message("⚠️ El sistema de sugerencias no está configurado del todo.", ephemeral=True)
        return

    canal_buzon = interaction.guild.get_channel(config["canal_buzon_id"])
    canal_staff = interaction.guild.get_channel(config["canal_staff_id"])
    if not canal_buzon or not canal_staff:
        await interaction.response.send_message("⚠️ No se encontraron los canales configurados.", ephemeral=True)
        return

    embed_publico = discord.Embed(
        title="💡 Nueva sugerencia",
        description=texto,
        color=discord.Color.blurple()
    )
    embed_publico.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)

    mensaje_publico = await canal_buzon.send(embed=embed_publico, view=VotosPublicoView())

    embed_staff = embed_publico.copy()
    await canal_staff.send(
        embed=embed_staff,
        view=VotosStaffView(mensaje_publico_id=mensaje_publico.id, canal_publico_id=canal_buzon.id)
    )

    await interaction.response.send_message("✅ Tu sugerencia fue enviada al buzón.", ephemeral=True)
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

@bot.tree.command(name="untimeout", description="Quita el silencio a un usuario")
@app_commands.checks.has_permissions(moderate_members=True)
async def untimeout(interaction: discord.Interaction, usuario: discord.Member):
    await usuario.timeout(None)
    await interaction.response.send_message(f"🔊 {usuario.mention} ya no está silenciado.")

@bot.tree.command(name="unban", description="Quita el baneo a un usuario")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str, motivo: str = "Sin motivo especificado"):
    usuario = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(usuario, reason=motivo)
    await interaction.response.send_message(f"✅ {usuario.mention} ha sido desbaneado.\nMotivo: {motivo}")

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
    await interaction.followup.send(f"✅ Se borraron {len(borrados)} mensajes.", ephemeral=True)

import os
TOKEN = os.environ.get('DISCORD_TOKEN')
bot.run(TOKEN)

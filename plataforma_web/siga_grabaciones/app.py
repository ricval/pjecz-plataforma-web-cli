"""
CLI SIGA Grabaciones App
"""
from datetime import datetime, timedelta
from pathlib import Path
import re
import subprocess

import rich
import typer

from common.exceptions import CLIAnyError
from config.settings import LIMIT

from .request_api import get_siga_grabaciones, post_siga_grabacion

ARCHIVO_NOMBRE_REGEXP = r"(\d{8})_(\d{6})_([A-Z0-1-]{1,16})_([A-Z0-1-]{1,16})_([A-Z]{3})_(\d{1,4}-\d{4}(-[A-Z-]+)?))"

encabezados = ["ID", "Inicio", "Sala", "Autoridad", "Expediente", "Duración", "Tamaño"]

app = typer.Typer()


@app.command()
def consultar(
    autoridad_id: int = None,
    autoridad_clave: str = None,
    distrito_id: int = None,
    distrito_clave: str = None,
    materia_id: int = None,
    materia_clave: str = None,
    siga_sala_id: int = None,
    siga_sala_clave: str = None,
    limit: int = LIMIT,
    offset: int = 0,
):
    """Consultar grabaciones"""
    rich.print("Consultar grabaciones...")

    # Solicitar datos
    try:
        respuesta = get_siga_grabaciones(
            autoridad_id=autoridad_id,
            autoridad_clave=autoridad_clave,
            distrito_id=distrito_id,
            distrito_clave=distrito_clave,
            materia_id=materia_id,
            materia_clave=materia_clave,
            siga_sala_id=siga_sala_id,
            siga_sala_clave=siga_sala_clave,
            limit=limit,
            offset=offset,
        )
    except CLIAnyError as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit()

    # Mostrar la tabla
    console = rich.console.Console()
    table = rich.table.Table()
    for enca in encabezados:
        table.add_column(enca)
    for registro in respuesta["items"]:
        inicio = datetime.strptime(registro["inicio"], "%Y-%m-%dT%H:%M:%S")
        duracion_segundos = timedelta(seconds=registro["duracion"])
        table.add_row(
            str(registro["id"]),
            inicio.strftime("%Y-%m-%d %H:%M:%S"),
            registro["siga_sala_clave"],
            registro["autoridad_clave"],
            registro["expediente"],
            f"{duracion_segundos} seg.",
            f"{registro['tamanio'] / (1024 * 1024):0.2f} MB",
        )
    console.print(table)

    # Mostrar el total
    rich.print(f"Total: [green]{respuesta['total']}[/green] grabaciones")


@app.command()
def crear(archivo: str):
    """Crea un nuevo registro de grabación"""
    rich.print("[bold cyan]=== Crear registro de grabación ===[/bold cyan]")

    # Validar con subprocess que exista el programa ffprobe
    try:
        process = subprocess.run(["ffprobe", "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    except FileNotFoundError as error:
        typer.secho("No se encuentra el programa 'ffprobe' para calcular la duración del video. " + str(error), fg=typer.colors.RED)
        raise typer.Exit()

    # Ruta completa al archivo
    archivo_ruta = Path(archivo)

    # Validar que exista el archivo
    if not archivo_ruta.is_file():
        typer.secho("No se encuentra el archivo", fg=typer.colors.RED)
        raise typer.Exit()

    # Obtener la extensión del archivo
    extension_archivo = archivo_ruta.suffix

    # Validar que la extensión sea .mp4
    if extension_archivo != ".mp4":
        typer.secho("El archivo debe tener la extensión .mp4", fg=typer.colors.RED)
        raise typer.Exit()

    # Obtener el nombre del archivo sin la extensión
    archivo_nombre = archivo_ruta.stem

    # Validar que el nombre del archivo cumpla con la expresión regular
    coincidencia = re.match(ARCHIVO_NOMBRE_REGEXP, archivo_nombre)
    if not coincidencia:
        typer.secho("El nombre del archivo no cumple con el formato requerido", fg=typer.colors.RED)
        raise typer.Exit()

    # Extraer del nombre del archivo la fecha y la hora de inicio
    inicio_str = coincidencia.group(1) + "T" + coincidencia.group(2)
    inicio_datetime = datetime.strptime(inicio_str, "%y%m%dT%H%M%S")

    # Extraer del nombre del archivo la clave de la sala
    siga_sala_clave = coincidencia.group(3)

    # Extraer del nombre del archivo la clave de la autoridad
    autoridad_clave = coincidencia.group(4)

    # Extraer del nombre del archivo la clave de la materia
    materia_clave = coincidencia.group(5)

    # Extraer del nombre del archivo el número de expediente
    expediente = coincidencia.group(6)

    # Obtener el tamaño del archivo con Pathlib
    tamanio = archivo_ruta.stat().st_size
    tamanio_str = f"{tamanio / (1024 * 1024):0.2f} MB"

    # Obtener la duración del archivo de video con ffprobe
    try:
        process = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", archivo_ruta], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
        duracion = timedelta(seconds=float(process.stdout))
    except:
        typer.secho("Error al ejecutar el programa 'ffprobe' para calcular la duración del video.", fg=typer.colors.RED)
        raise typer.Exit()

    # Calcular el término sumando el inicio y la duracion
    termino_datetime = inicio_datetime + duracion
    termino_str = termino_datetime.strftime("%Y/%m/%dT%H:%M:%S")

    # Definir la ruta
    justicia_ruta = archivo

    # Mostrar Metadatos
    rich.print(f"Autoridad Clave: [yellow]{autoridad_clave}[/yellow]")
    rich.print(f"SIGA Sala Clave: [yellow]{siga_sala_clave}[/yellow]")
    rich.print(f"Materia Clave:   [yellow]{materia_clave}[/yellow]")
    rich.print(f"Expediente:      [yellow]{expediente}[/yellow]")
    rich.print(f"Inicio:          [yellow]{inicio_str}[/yellow]")
    rich.print(f"Termino:         [yellow]{termino_str}[/yellow]")
    rich.print(f"Archivo:         [yellow]{archivo_nombre}[/yellow]")
    rich.print(f"Justicia Ruta:   [yellow]{justicia_ruta}[/yellow]")
    rich.print(f"Tamaño:          [yellow]{tamanio_str}[/yellow]")
    rich.print(f"Duración:        [yellow]{duracion}[/yellow]")

    # Enviar datos
    rich.print("[cyan]- Envío de información.[/cyan]")
    try:
        respuesta = post_siga_grabacion(
            autoridad_clave=autoridad_clave,
            siga_sala_clave=siga_sala_clave,
            materia_clave=materia_clave,
            expediente=expediente,
            inicio=inicio_datetime,
            termino=termino_datetime,
            archivo_nombre=archivo_nombre,
            justicia_ruta=justicia_ruta,
            tamanio=tamanio,
            duracion=duracion,
        )
    except CLIAnyError as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit()

    # Si la respuesta es exitosa
    if respuesta["success"] is True:
        rich.print(f"Grabación creada con ID [green]{respuesta['id']}[/green]")
        rich.print(f"Mensaje: [cyan]{respuesta['message']}[/cyan]")
    else:
        typer.secho(f"No se creo la grabación por: {respuesta['message']}", fg=typer.colors.RED)
        raise typer.Exit()

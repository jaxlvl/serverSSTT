# coding=utf-8
#!/usr/bin/env python3

import socket
import selectors    #https://docs.python.org/3/library/selectors.html
import select
import types        # Para definir el tipo de datos data
import argparse     # Leer parametros de ejecución
import os           # Obtener ruta y extension
from datetime import datetime, timedelta # Fechas de los mensajes HTTP
import time         # Timeout conexión
import sys          # sys.exit
import re           # Analizador sintáctico
import logging      # Para imprimir logs

from urllib.parse import unquote




BUFSIZE = 8192 # Tamaño máximo del buffer que se puede utilizar
TIMEOUT_CONNECTION = 1 + 9 + 4 + 4 + 10 # Timout para la conexión persistente
MAX_ACCESOS = 10
Cabeceras = ["Host", "User-Agent", "Accept", "Keep-Alive", "Connection"]
codigos = {
    301: "Moved Permanently",
    400: "Bad Request",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    505: "HTTP Version Not Supported"
}


XX = "19"
YY = "44"
URL = "web.servitel" + XX + YY + ".org"
COOKIE_COUNTER = "cookie_counter_" + XX + YY


# Extensiones admitidas (extension, name in HTTP)
filetypes = {"gif":"image/gif", "jpg":"image/jpg", "jpeg":"image/jpeg", "png":"image/png", "htm":"text/htm", 
             "html":"text/html", "css":"text/css", "js":"text/js"}

# Configuración de logging
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s.%(msecs)03d] [%(levelname)-7s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger()


def enviar_mensaje(cs, data):
    """ Esta función envía datos (data) a través del socket cs
        Devuelve el número de bytes enviados.
    """
    if isinstance(data, (bytes, bytearray)):
        cs.send(data)
    else: cs.send(data.encode())
    pass


def recibir_mensaje(cs):
    """ Esta función recibe datos a través del socket cs
        Leemos la información que nos llega. recv() devuelve un string con los datos.
    """
    return cs.recv(BUFSIZE).decode()


def cerrar_conexion(cs):
    """ Esta función cierra una conexión activa.
    """
    cs.close()
    pass


def process_cookies(cookie_header):
    """ Esta función procesa la cookie cookie_counter
        1. Se analizan las cabeceras en headers para buscar la cabecera Cookie
        2. Una vez encontrada una cabecera Cookie se comprueba si el valor es cookie_counter
        3. Si no se encuentra cookie_counter , se devuelve 1
        4. Si se encuentra y tiene el valor MAX_ACCESSOS se devuelve MAX_ACCESOS
        5. Si se encuentra y tiene un valor 1 <= x < MAX_ACCESOS se incrementa en 1 y se devuelve el valor
    """
    if cookie_header != "":
        cookie = cookie_header.split("=")
        if cookie[0] == COOKIE_COUNTER:
            accesos = int(cookie[1])
            if accesos == MAX_ACCESOS:
                return MAX_ACCESOS
            elif 1 <= accesos and accesos < MAX_ACCESOS: 
                return accesos + 1       
    else:
        return 1
    
def construir_msg_email(email):
    gif_url = "./email_gif.gif"
    html_content = """
    <html>
    <head><title>Email</title></head>
    <body>
        <h1>Email correcto</h1>
        <p>El email {} es correcto.</p>
        <img src="{}" alt="Email GIF">
    </body>
    </html>
    """.format(email, gif_url)

    snd_msg = "HTTP/1.1 200 OK\r\n" + \
        "Date: " + datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n" + \
        "Server: " + URL + "\r\n" + \
        "Content-Type: " + filetypes["html"] + "\r\n" + \
        "Content-Length: " + str(len(html_content)) + "\r\n" + \
        "\r\n" + \
        html_content
        
    return snd_msg

def construir_msg_email_incorrecto(email):
    gif_url = "./denegado_gif.gif"
    html_content = """
    <html>
    <head><title>Email</title></head>
    <body>
        <h1>403 Forbiden</h1>
        <p>El email {} no es correcto.</p>
        <img src="{}" alt="Email GIF">
    </body>
    </html>
    """.format(email, gif_url)

    snd_msg = "HTTP/1.1 403 "+ codigos[403]+"\r\n" + \
        "Date: " + datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n" + \
        "Server: " + URL + "\r\n" + \
        "Content-Type: " + filetypes["html"] + "\r\n" + \
        "Content-Length: " + str(len(html_content)) + "\r\n" + \
        "\r\n" + \
        html_content
        
    return snd_msg

#método para construir mensajes conocidos de error
def construir_msg_error(x):
    gif_url = "./error_gif.gif"
    html_content = """
    <html>
    <head><title>Error {}</title></head>
    <body>
        <h1>{} {}</h1>
        <p>Lo sentimos, ocurrio un error.</p>
        <img src="{}" alt="Error GIF">
    </body>
    </html>
    """.format(x, x, codigos[x], gif_url)

    snd_msg = "HTTP/1.1 " + str(x) + " " + codigos[x]+ "\r\n" + \
        "Date: " + datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n" + \
        "Server: " + URL + "\r\n" + \
        "Content-Type: " + filetypes["html"] + "\r\n" + \
        "Content-Length: " + str(len(html_content)) + "\r\n" + \
        "\r\n" + \
        html_content
        
    return snd_msg


def process_web_request(cs, webroot):
    """ Procesamiento principal de los mensajes recibidos.
        Típicamente se seguirá un procedimiento similar al siguiente (aunque el alumno puede modificarlo si lo desea)

        * Bucle para esperar hasta que lleguen datos en la red a través del socket cs con select()

            * Se comprueba si hay que cerrar la conexión por exceder TIMEOUT_CONNECTION segundos
              sin recibir ningún mensaje o hay datos. Se utiliza select.select

            * Si no es por timeout y hay datos en el socket cs.
                * Leer los datos con recv.
                * Analizar que la línea de solicitud y comprobar está bien formateada según HTTP 1.1
                    * Devuelve una lista con los atributos de las cabeceras.
                    * Comprobar si la versión de HTTP es 1.1
                    * Comprobar si es un método GET o POST. Si no devolver un error Error 405 "Method Not Allowed".
                    * Leer URL y eliminar parámetros si los hubiera
                    * Comprobar si el recurso solicitado es /, En ese caso el recurso es index.html
                    * Construir la ruta absoluta del recurso (webroot + recurso solicitado)
                    * Comprobar que el recurso (fichero) existe, si no devolver Error 404 "Not found"
                    * Analizar las cabeceras. Imprimir cada cabecera y su valor. Si la cabecera es Cookie comprobar
                      el valor de cookie_counter para ver si ha llegado a MAX_ACCESOS.
                      Si se ha llegado a MAX_ACCESOS devolver un Error "403 Forbidden"
                    * Obtener el tamaño del recurso en bytes.
                    * Extraer extensión para obtener el tipo de archivo. Necesario para la cabecera Content-Type
                    * Preparar con código 200. Construir una respuesta que incluya: la línea de respuesta y
                      las cabeceras Date, Server, Connection, Set-Cookie (para la cookie cookie_counter),
                      Content-Length y Content-Type.
                    * Leer y enviar el contenido del fichero a retornar en el cuerpo de la respuesta.
                    * Se abre el fichero en modo lectura y modo binario
                        * Se lee el fichero en bloques de BUFSIZE bytes (8KB)
                        * Cuando ya no hay más información para leer, se corta el bucle

            * Si es por timeout, se cierra el socket tras el período de persistencia.
                * NOTA: Si hay algún error, enviar una respuesta de error con una pequeña página HTML que informe del error.
    """
    #datos = recibir_mensaje(cs)
    #print(datos)
    rlist = [cs]
    wlist = []
    xlist = []
    #Hay que controlar el número de accesos
    accesos = 0
    recv_msg = "a"
    salir = False
    while accesos < MAX_ACCESOS and recv_msg != "" and not salir:
        rsublist, wsublist, xsublist = select.select(rlist, wlist, xlist, TIMEOUT_CONNECTION)
        if rsublist == rlist:
            recv_msg = recibir_mensaje(cs)
            if recv_msg != "":
                print(recv_msg) #HAY QUE IMPRIMIR EL MENSAJE QUE LLEGA????
                
                lineas = recv_msg.splitlines()
                solicitud = lineas[0].split()
                body_index = lineas.index("")
                body = "\n".join(lineas[body_index + 1:])  # Unir las líneas del cuerpo
                
                #procesamos la petición:
                if len(solicitud)==3:
                    comand, URL_req, http_version = solicitud[0], solicitud[1], solicitud[2]
                else:
                    print("codificar error cabecera o valores por defecto", file=sys.stderr)
                
                if http_version != "HTTP/1.1":
                    print("Versión de HTTP distinta de 1.1")
                    #posiblemente construir mensaje con código 505.
                if comand != "GET" and comand != "POST":
                        snd_msg = construir_msg_email(405)
                        enviar_mensaje(cs, snd_msg)
                        return 
                #* Leer URL y eliminar parámetros si los hubiera
                URL_seg = URL_req.split("?")
                path = URL_seg[0]
                parametros = ""
                if(len(URL_seg)>1):
                    parametros = URL_seg[1:] #ALMACENO LOS PARÁMETROS POR SI UN CASO SI NO, BORRAR
                    
                #* Comprobar si el recurso solicitado es /, En ese caso el recurso es index.html
                if(path=="/"):
                    path = "/index.html"
                # Construir la ruta absoluta del recurso (webroot + recurso solicitado)
                ruta = webroot + path
                
                #Comprobar que el recurso (fichero) existe, si no devolver Error 404 "Not found"
                if not os.path.isfile(ruta) and comand!="POST": #IMPORTANTE VER SI TIENE QUE EXISTIR EL FICHERO CUANDO SE HACE POST, PORQUE ERROR
                    snd_msg = construir_msg_error(404)
                    enviar_mensaje(cs, snd_msg)
                    return 
                    
                #Analizar las cabeceras. Imprimir cada cabecera y su valor. Si la cabecera es Cookie comprobar
                #el valor de cookie_counter para ver si ha llegado a MAX_ACCESOS.
                #Si se ha llegado a MAX_ACCESOS devolver un Error "403 Forbidden"
                flag_cookie = False
                #procesamos las cabeceras
                for cabecera in lineas[1:body_index]: 
                    cadena = cabecera.split(sep = ':', maxsplit=1)
                    print("He encontrado la siguiente cabecera:", cadena[0])
                    
                    cadena[1] = cadena[1][1:]
                    
                    print(" Con el siguiente valor: ", cadena[1])
                    if cadena[0] == "Cookie":
                        set_cookie_count = process_cookies(cadena[1])
                        flag_cookie = True
                        if set_cookie_count == MAX_ACCESOS:
                            snd_msg = construir_msg_error(403)
                            enviar_mensaje(cs, snd_msg)
                            return 
                    
                print()
                if(not flag_cookie):
                    set_cookie_count=1
                # Obtener el tamaño del recurso en bytes.
                #IMPORTANTE MIRAR SI ESTO ES ÚNICAMENTE NECESARIO CUANDO ES UN GET, PORQUE ERROR CON EL POST
                if comand!="POST":
                    size_bytes = os.stat(ruta).st_size
                    #Extraer extensión para obtener el tipo de archivo. Necesario para la cabecera Content-Type
                    ext = path.split(".")[-1]

                #Procesamiento de POST
                post_snd_body = ""
                if comand == "POST":
                    match = re.search(r'email=([^&\s]+)', body)  # Buscar email en el cuerpo
                    if not match:
                        snd_msg = construir_msg_error(403)  # Error si no hay email
                        #enviar_mensaje(cs, snd_msg.encode())
                        enviar_mensaje(cs, snd_msg)
                        return
                    
                    email = match.group(1)  # Extraer email
                    email = unquote(email)
                    #Validar email: un solo @ y termina en @um.es
                    if email.count("@") != 1 or not email.endswith("@um.es"):
                        snd_msg = construir_msg_email_incorrecto(email)  # Error 403 si email no es válido
                        enviar_mensaje(cs, snd_msg)
                        return
                    post_snd_msg = construir_msg_email(email)
                    print ("\n\n\n " + post_snd_msg + "\n\n\n")
                    enviar_mensaje(cs, post_snd_msg)
                    return
                #Preparar respuesta con código 200. Construir una respuesta que incluya: la línea de respuesta y
                #las cabeceras Date, Server, Connection, Set-Cookie (para la cookie cookie_counter),
                #Content-Length y Content-Type.
                
                """Leer y enviar el contenido del fichero a retornar en el cuerpo de la respuesta.
                Se abre el fichero en modo lectura y modo binario
                Se lee el fichero en bloques de BUFSIZE bytes (8KB)
                Cuando ya no hay más información para leer, se corta el bucle"""
                snd_msg = "HTTP/1.1 200 OK\r\n" + \
                        "Date: " + datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n" + \
                        "Server: " + URL + "\r\n" + \
                        "Content-Type: " + filetypes[ext] + "\r\n" + \
                        "Content-Length: " + str(size_bytes) + "\r\n" + \
                        "Connection: Keep-Alive" + "\r\n" + \
                        "Keep-Alive: timeout=" + str(TIMEOUT_CONNECTION) + " max=" + str(MAX_ACCESOS) + "\r\n" + \
                        "Set-Cookie: " + COOKIE_COUNTER + "=" + str(set_cookie_count) + "\r\n" + \
                        "\r\n"
                
                """
                #Añadir cuerpo POST si existe
                if post_snd_body != "":
                    snd_msg = snd_msg + post_snd_body
                """

                enviar_mensaje(cs, snd_msg)
                
                bytes_read = 0
                f = open(ruta, "rb")
                while bytes_read < size_bytes:
                    bytes_to_read = min(size_bytes-bytes_read, BUFSIZE)
                    bytes_read += bytes_to_read
                    
                    cont_f = f.read(bytes_to_read)
                    snd_msg_bin =cont_f 
    
                    enviar_mensaje(cs, snd_msg_bin)
                print("Enviados ", bytes_read, " bytes\n")  
                f.close()
            else:
                salir = True
        else:
            salir = True
        accesos+=1
    
def main():
    """ Función principal del servidor
    """

    try:

        # Argument parser para obtener la ip y puerto de los parámetros de ejecución del programa. IP por defecto 0.0.0.0
        parser = argparse.ArgumentParser()
        parser.add_argument("-p", "--port", help="Puerto del servidor", type=int, required=True)
        parser.add_argument("-ip", "--host", help="Dirección IP del servidor o localhost", required=True)
        parser.add_argument("-wb", "--webroot", help="Directorio base desde donde se sirven los ficheros (p.ej. /home/user/mi_web)")
        parser.add_argument('--verbose', '-v', action='store_true', help='Incluir mensajes de depuración en la salida')
        args = parser.parse_args()


        if args.verbose:
            logger.setLevel(logging.DEBUG)

        logger.info('Enabling server in address {} and port {}.'.format(args.host, args.port))

        logger.info("Serving files from {}".format(args.webroot))

        """ Funcionalidad a realizar
        * Crea un socket TCP (SOCK_STREAM)
        * Permite reusar la misma dirección previamente vinculada a otro proceso. Debe ir antes de sock.bind
        * Vinculamos el socket a una IP y puerto elegidos

        * Escucha conexiones entrantes

        * Bucle infinito para mantener el servidor activo indefinidamente
            - Aceptamos la conexión

            - Creamos un proceso hijo

            - Si es el proceso hijo se cierra el socket del padre y procesar la petición con process_web_request()

            - Si es el proceso padre cerrar el socket que gestiona el hijo.
        """
        serverSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0)
        serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        serverSocket.bind((args.host, args.port))

        serverSocket.listen()

        while (True):
            socketHijo, dirCliente = serverSocket.accept()

            pid = os.fork()

            if (pid == 0):
                # SE CIERRA EL SOCKET DEL PROCESO PADRE
                cerrar_conexion(serverSocket)

                # SE PROCESA LA PETICIÓN
                process_web_request(socketHijo, args.webroot)
                cerrar_conexion(socketHijo)

                exit(0)
            else:
                #print("Flag. Proceso hijo: " + str(pid))
                cerrar_conexion(socketHijo)
    except KeyboardInterrupt:
        True

if __name__== "__main__":
    main()
    

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



BUFSIZE = 8192 # Tamaño máximo del buffer que se puede utilizar
TIMEOUT_CONNECTION = 1 + 9 + 4 + 4 + 10 # Timout para la conexión persistente
TIMEOUT_CONNECTION = 3 # Timout para la conexión persistentePARA BORRAR
MAX_ACCESOS = 10
Cabeceras = ["Host", "User-Agent", "Accept", "Keep-Alive", "Connection"]
D = {} #Diccionario vacío


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
    cs.send(data.encode())
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


def process_cookies(headers,  cs):
    """ Esta función procesa la cookie cookie_counter
        1. Se analizan las cabeceras en headers para buscar la cabecera Cookie
        2. Una vez encontrada una cabecera Cookie se comprueba si el valor es cookie_counter
        3. Si no se encuentra cookie_counter , se devuelve 1
        4. Si se encuentra y tiene el valor MAX_ACCESSOS se devuelve MAX_ACCESOS
        5. Si se encuentra y tiene un valor 1 <= x < MAX_ACCESOS se incrementa en 1 y se devuelve el valor
    """
    for line in headers:
        line = str(line)
        line.strip(" ")
    pass

def subprocess_web_request(recv_msg):
    lineas = recv_msg.splitlines()
    solicitud = lineas[0].split()
    body_index = lineas.index("")
    
    #procesamos la petición:
    comand, path, http_version = solicitud[0], solicitud[1], solicitud[2]
    
    #procesamos las cabeceras
    for cabecera in lineas[1:body_index]: 
        cadena = cabecera.split(sep = ':')
        if cadena[0] in Cabeceras:
            print(cadena[0])
            D[cadena[0]] = cadena[1]
    
    #procesamos el cuerpo
    body = ""
    if body_index + 1 < lineas.length():
        for linea in lineas[body_index + 1:]:
            body = body + linea
            
    
    respuesta = "HTTP/1.1 200 OK\r\n" + "Content-Type: text/plain\r\n" + "Content-Length: 11\r\n\r\n" + "Hola mundo"
    return respuesta

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
                    * Preparar respuesta con código 200. Construir una respuesta que incluya: la línea de respuesta y
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
    #HAy que controlar el número de accesos
    accesos = 0
    recv_msg = "a"
    salir = False
    while accesos < MAX_ACCESOS and recv_msg != "" and not salir:
        rsublist, wsublist, xsublist = select.select(rlist, wlist, xlist, TIMEOUT_CONNECTION)
        if rsublist == rlist:
            recv_msg = recibir_mensaje(cs)
            if recv_msg != "":
                print(recv_msg)
                snd_msg = subprocess_web_request(recv_msg)
                enviar_mensaje(cs, snd_msg)
            else:
                salir = True
        else:
            salir = True
        accesos+=1
    #print("salgo del while de procesar")
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
    

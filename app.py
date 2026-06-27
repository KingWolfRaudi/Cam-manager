from flask import Flask, render_template, Response, request
import cv2
import datetime
import time
import threading
import os
import json
import requests

app = Flask(__name__)

# --- CONFIGURACIÓN ---
def cargar_config():
    with open('config.json', 'r') as f:
        return json.load(f)

config = cargar_config()

CARPETA_CAPTURAS = '/mnt/sd/Cam-capturas'

# --- NOTIFICACIONES ---
def enviar_notificacion_telegram(mensaje):
    print(f"DEBUG: Intentando enviar notificación a Telegram: {mensaje}", flush=True)
    url = f"https://api.telegram.org/bot{config['telegram_token']}/sendMessage"
    payload = {
        "chat_id": config['chat_id'],
        "text": mensaje
    }
    try:
        respuesta = requests.post(url, data=payload)
        print(f"DEBUG: Respuesta recibida: {respuesta.status_code}", flush=True)
        if respuesta.status_code == 200:
            print("Notificación enviada con éxito.", flush=True)
        else:
            print(f"Error al enviar notificación. Código: {respuesta.status_code}, Respuesta: {respuesta.text}", flush=True)
    except Exception as e:
        print(f"Error enviando notificación: {e}", flush=True)

def enviar_video_telegram(ruta_video):
    print(f"DEBUG: Intentando enviar video a Telegram: {ruta_video}", flush=True)
    url = f"https://api.telegram.org/bot{config['telegram_token']}/sendVideo"
    
    try:
        with open(ruta_video, 'rb') as video_file:
            payload = {
                "chat_id": config['chat_id']
            }
            files = {
                "video": video_file
            }
            respuesta = requests.post(url, data=payload, files=files)
            
        print(f"DEBUG: Respuesta video recibida: {respuesta.status_code}", flush=True)
        if respuesta.status_code == 200:
            print("Video enviado con éxito.", flush=True)
        else:
            print(f"Error al enviar video. Código: {respuesta.status_code}, Respuesta: {respuesta.text}", flush=True)
    except Exception as e:
        print(f"Error enviando video: {e}", flush=True)

# --- VARIABLES GLOBALES ---
frame_actual = None
ultimo_frame_guardado = None
grabando = False
video_writer = None
ruta_grabacion_actual = None # Nueva variable
tiempo_inicio_grabacion = 0 # Nueva variable
resolucion_ancho = 640
resolucion_alto = 480
actualizar_camara = False
camara_activa = False
camara_index = 0
modo_deteccion = False
ultima_deteccion = 0
background_frame = None

def capturar_camara_fondo():
    global frame_actual, ultimo_frame_guardado, grabando, video_writer, ruta_grabacion_actual, tiempo_inicio_grabacion, resolucion_ancho, resolucion_alto, actualizar_camara, camara_activa, camara_index, modo_deteccion, ultima_deteccion, background_frame
    
    camara = None 
    index_actual = -1
    
    while True:
        if camara_activa:
            if camara is None or index_actual != camara_index:
                if camara is not None:
                    camara.release()
                print(f"Intentando abrir la cámara {camara_index}...", flush=True)
                camara = cv2.VideoCapture(camara_index)
                index_actual = camara_index
                if not camara.isOpened():
                    print("Error: No se pudo abrir la cámara.", flush=True)
                    camara = None
                else:
                    print("Cámara abierta exitosamente.", flush=True)
                
                if camara:
                    camara.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    camara.set(cv2.CAP_PROP_FRAME_WIDTH, resolucion_ancho)
                    camara.set(cv2.CAP_PROP_FRAME_HEIGHT, resolucion_alto)
            
            if actualizar_camara:
                camara.set(cv2.CAP_PROP_FRAME_WIDTH, resolucion_ancho)
                camara.set(cv2.CAP_PROP_FRAME_HEIGHT, resolucion_alto)
                actualizar_camara = False

            exito, frame = camara.read()
            if exito:
                frame = cv2.flip(frame, 1)
                frame_actual = frame.copy()
                ultimo_frame_guardado = frame.copy()
                
                # --- LÓGICA DE DETECCIÓN DE MOVIMIENTO ---
                if modo_deteccion:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.GaussianBlur(gray, (21, 21), 0)
                    
                    if background_frame is None:
                        background_frame = gray
                    else:
                        delta = cv2.absdiff(background_frame, gray)
                        thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
                        thresh = cv2.dilate(thresh, None, iterations=2)
                        
                        movimiento_detectado = cv2.countNonZero(thresh)
                        
                        if movimiento_detectado > 25000: # Umbral de sensibilidad aumentado
                            if not grabando:
                                print(f"DEBUG: Movimiento detectado ({movimiento_detectado}), iniciando grabación...", flush=True)
                                grabando = True
                                tiempo_inicio_grabacion = time.time()
                                enviar_notificacion_telegram("⚠️ Movimiento detectado. Grabando...")
                                ultima_deteccion = time.time()
                else:
                    if background_frame is not None:
                         background_frame = None # Reset cuando no hay deteccion

                # --- LÓGICA DE GRABACIÓN ---
                if grabando:
                    if video_writer is None:
                        codigo_video = cv2.VideoWriter_fourcc(*'mp4v')
                        nombre_archivo = datetime.datetime.now().strftime("video_%Y%m%d_%H%M%S.mp4")
                        ruta_grabacion_actual = os.path.join(CARPETA_CAPTURAS, nombre_archivo)
                        video_writer = cv2.VideoWriter(ruta_grabacion_actual, codigo_video, 20.0, (resolucion_ancho, resolucion_alto))
                    
                    video_writer.write(frame)
                    
                    # Detener grabación automática después de 10 segundos
                    if time.time() - tiempo_inicio_grabacion > 10:
                        print("DEBUG: Grabación automática finalizada (10s).", flush=True)
                        grabando = False
                        video_writer.release()
                        video_writer = None
                        enviar_video_telegram(ruta_grabacion_actual)
                        ruta_grabacion_actual = None
                else:
                    if video_writer is not None:
                        video_writer.release()
                        video_writer = None
                        ruta_grabacion_actual = None
        else:
            if camara is not None:
                camara.release()
                camara = None
                frame_actual = None
                background_frame = None
                
                if grabando:
                    grabando = False
                    if video_writer is not None:
                        video_writer.release()
                        video_writer = None
                        
        time.sleep(0.01)

def generar_frames():
    global frame_actual, camara_activa
    while True:
        if camara_activa and frame_actual is not None:
            parametros_jpg = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            ret, buffer = cv2.imencode('.jpg', frame_actual, parametros_jpg)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            time.sleep(0.5)
            
        time.sleep(0.03)

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/toggle_deteccion', methods=['POST'])
def toggle_deteccion():
    global modo_deteccion
    modo_deteccion = not modo_deteccion
    print(f"DEBUG: Detección de movimiento cambiada a: {modo_deteccion}", flush=True)
    return "activa" if modo_deteccion else "desactivada", 200

@app.route('/toggle_camara', methods=['POST'])
def toggle_camara():
    global camara_activa
    camara_activa = not camara_activa
    return "encendida" if camara_activa else "apagada", 200

@app.route('/tomar_foto', methods=['POST'])
def tomar_foto():
    global ultimo_frame_guardado, camara_activa
    if not camara_activa:
        return "Cámara apagada", 400
    if ultimo_frame_guardado is not None:
        # Guardamos la foto en la ruta absoluta
        nombre_archivo = datetime.datetime.now().strftime("foto_%Y%m%d_%H%M%S.jpg")
        ruta_completa = os.path.join(CARPETA_CAPTURAS, nombre_archivo)
        cv2.imwrite(ruta_completa, ultimo_frame_guardado)
        return "Foto guardada", 200
    return "Error", 500

@app.route('/toggle_video', methods=['POST'])
def toggle_video():
    global grabando, camara_activa
    if not camara_activa:
        return "Cámara apagada", 400
    
    grabando = not grabando 
    return "grabando" if grabando else "detenido", 200

@app.route('/set_resolucion', methods=['POST'])
def set_resolucion():
    global resolucion_ancho, resolucion_alto, actualizar_camara
    datos = request.get_json()
    resolucion_ancho = int(datos['ancho'])
    resolucion_alto = int(datos['alto'])
    actualizar_camara = True
    return "Resolución actualizada", 200

@app.route('/listar_camaras', methods=['GET'])
def listar_camaras():
    camaras = []
    parent_devices = {}
    
    for i in range(10):
        dev_path = f'/sys/class/video4linux/video{i}'
        if os.path.exists(dev_path):
            # Obtener la ruta real del dispositivo físico (el padre USB)
            real_path = os.path.realpath(dev_path)
            # Extraer solo la parte del dispositivo USB (ej: .../usb1/1-3/1-3:1.0/)
            parent = '/'.join(real_path.split('/')[:-1])
            
            if parent not in parent_devices:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    camaras.append(i)
                    parent_devices[parent] = i
                    cap.release()
                    
    return {"camaras": camaras}, 200

@app.route('/set_camara', methods=['POST'])
def set_camara():
    global camara_index
    datos = request.get_json()
    camara_index = int(datos['index'])
    return "Cámara cambiada", 200

if __name__ == '__main__':
    hilo = threading.Thread(target=capturar_camara_fondo)
    hilo.daemon = True
    hilo.start()
    app.run(host='0.0.0.0', port=5000, threaded=True)

from flask import Flask, render_template, Response, request
import cv2
import datetime
import os
import time

app = Flask(__name__)

# --- VARIABLES GLOBALES ---
ultimo_frame = None
grabando = False
video_writer = None

# Nuevas variables para controlar la resolución
resolucion_ancho = 640
resolucion_alto = 480
actualizar_camara = False # Este "interruptor" le avisará al bucle que debe cambiar el tamaño

def generar_frames():
    global ultimo_frame, grabando, video_writer, resolucion_ancho, resolucion_alto, actualizar_camara
    
    camara = cv2.VideoCapture(0)
    camara.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    # Configuramos la resolución inicial
    camara.set(cv2.CAP_PROP_FRAME_WIDTH, resolucion_ancho)
    camara.set(cv2.CAP_PROP_FRAME_HEIGHT, resolucion_alto)
    
    while True:
        # Si el usuario cambió la resolución en la página web, aplicamos el cambio
        if actualizar_camara:
            camara.set(cv2.CAP_PROP_FRAME_WIDTH, resolucion_ancho)
            camara.set(cv2.CAP_PROP_FRAME_HEIGHT, resolucion_alto)
            actualizar_camara = False # Apagamos el interruptor hasta el próximo cambio

        exito, frame = camara.read()
        if not exito:
            break
        else:
            frame = cv2.flip(frame, 1)
            ultimo_frame = frame.copy()
            
            if grabando:
                if video_writer is None:
                    codigo_video = cv2.VideoWriter_fourcc(*'mp4v')
                    nombre_video = datetime.datetime.now().strftime("capturas/video_%Y%m%d_%H%M%S.mp4")
                    # Usamos la resolución actual para guardar el video correctamente
                    video_writer = cv2.VideoWriter(nombre_video, codigo_video, 20.0, (resolucion_ancho, resolucion_alto))
                video_writer.write(frame)
            else:
                if video_writer is not None:
                    video_writer.release()
                    video_writer = None

            parametros_jpg = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            ret, buffer = cv2.imencode('.jpg', frame, parametros_jpg)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            time.sleep(0.03) 

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/tomar_foto', methods=['POST'])
def tomar_foto():
    global ultimo_frame
    if ultimo_frame is not None:
        nombre_foto = datetime.datetime.now().strftime("capturas/foto_%Y%m%d_%H%M%S.jpg")
        cv2.imwrite(nombre_foto, ultimo_frame)
        return "Foto guardada", 200
    return "Error", 500

@app.route('/toggle_video', methods=['POST'])
def toggle_video():
    global grabando
    grabando = not grabando 
    if grabando:
        return "grabando", 200
    else:
        return "detenido", 200

# --- NUEVA RUTA PARA CAMBIAR LA RESOLUCIÓN ---
@app.route('/set_resolucion', methods=['POST'])
def set_resolucion():
    global resolucion_ancho, resolucion_alto, actualizar_camara
    # Recibimos los datos en formato JSON desde JavaScript
    datos = request.get_json()
    
    # Actualizamos nuestras variables globales
    resolucion_ancho = int(datos['ancho'])
    resolucion_alto = int(datos['alto'])
    actualizar_camara = True # Encendemos el interruptor
    
    return "Resolución actualizada", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
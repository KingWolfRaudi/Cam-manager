from flask import Flask, render_template, Response, request
import cv2
import datetime
import os

app = Flask(__name__)

# --- VARIABLES GLOBALES ---
# Estas variables nos permiten compartir información entre la transmisión de video y los botones
ultimo_frame = None
grabando = False
video_writer = None

def generar_frames():
    global ultimo_frame, grabando, video_writer
    
    camara = cv2.VideoCapture(0)
    camara.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camara.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camara.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    while True:
        exito, frame = camara.read()
        if not exito:
            break
        else:
            # 1. EFECTO ESPEJO: Volteamos el frame horizontalmente (el 1 significa eje Y)
            frame = cv2.flip(frame, 1)
            
            # Guardamos una copia del frame actual por si el usuario quiere tomar una foto
            ultimo_frame = frame.copy()
            
            # 2. GRABACIÓN DE VIDEO: Si el botón de grabar está activo, guardamos el frame
            if grabando:
                if video_writer is None:
                    # Si acabamos de empezar, configuramos el archivo de video .mp4
                    codigo_video = cv2.VideoWriter_fourcc(*'mp4v')
                    nombre_video = datetime.datetime.now().strftime("capturas/video_%Y%m%d_%H%M%S.mp4")
                    # Pasamos el nombre, códec, fotogramas por segundo (20.0) y resolución (640x480)
                    video_writer = cv2.VideoWriter(nombre_video, codigo_video, 20.0, (640, 480))
                
                # Escribimos el frame actual en el archivo de video
                video_writer.write(frame)
            else:
                # Si no estamos grabando, nos aseguramos de cerrar el archivo si estaba abierto
                if video_writer is not None:
                    video_writer.release()
                    video_writer = None

            # Preparamos el frame para enviarlo al navegador web
            parametros_jpg = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            ret, buffer = cv2.imencode('.jpg', frame, parametros_jpg)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# --- NUEVAS RUTAS PARA LOS BOTONES ---

@app.route('/tomar_foto', methods=['POST'])
def tomar_foto():
    global ultimo_frame
    if ultimo_frame is not None:
        # Generamos un nombre único usando la fecha y hora actual
        nombre_foto = datetime.datetime.now().strftime("capturas/foto_%Y%m%d_%H%M%S.jpg")
        # Guardamos la imagen en el disco duro
        cv2.imwrite(nombre_foto, ultimo_frame)
        return "Foto guardada exitosamente", 200
    return "Error al guardar foto", 500

@app.route('/toggle_video', methods=['POST'])
def toggle_video():
    global grabando
    # Invertimos el estado: si era falso (no grababa), ahora es verdadero (graba), y viceversa
    grabando = not grabando 
    
    # Le respondemos al navegador en qué estado quedamos
    if grabando:
        return "grabando", 200
    else:
        return "detenido", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)